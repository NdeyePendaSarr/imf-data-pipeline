-- Balance mensuelle à 6 colonnes (H5), une ligne par compte × agence × fin de mois de l'exercice :
-- solde d'ouverture D/C, mouvements du mois D/C, solde de clôture D/C.
--   Ouverture de janvier = 0 (première année, pas d'à-nouveaux) ; l'apport en capital est un
--   mouvement de janvier (journal OUV). Ouverture du mois m = clôture du mois m − 1.
--   Densification (H6) : une ligne par mois dès le premier mouvement du compte dans l'agence,
--   même sans mouvement le mois suivant (un compte au solde non nul ne disparaît pas).
--   Le solde est présenté du côté où il tombe (débiteur ou créditeur), sans compensation.

with fins_de_mois as (
    select date as date_fin_mois
    from {{ ref('dim_date') }}
    where dans_exercice and est_fin_de_mois
),

mouvements as (
    select
        code_compte,
        id_agence,
        (date_trunc('month', date_ecriture) + interval '1 month - 1 day')::date as date_fin_mois,
        sum(debit) as mouvement_debit,
        sum(credit) as mouvement_credit
    from {{ ref('fct_ecritures') }}
    group by 1, 2, 3
),

grille as (
    -- Chaque compte × agence, de son premier mois de mouvement jusqu'à décembre.
    select premiers.code_compte, premiers.id_agence, f.date_fin_mois
    from (
        select code_compte, id_agence, min(date_fin_mois) as premier_mois
        from mouvements
        group by 1, 2
    ) as premiers
    inner join fins_de_mois as f on f.date_fin_mois >= premiers.premier_mois
),

soldes as (
    select
        g.date_fin_mois,
        g.code_compte,
        g.id_agence,
        coalesce(m.mouvement_debit, 0) as mouvement_debit,
        coalesce(m.mouvement_credit, 0) as mouvement_credit,
        -- Solde net (débit − crédit) cumulé jusqu'à la fin du mois.
        sum(coalesce(m.mouvement_debit, 0) - coalesce(m.mouvement_credit, 0)) over (
            partition by g.code_compte, g.id_agence order by g.date_fin_mois
        ) as solde_cloture
    from grille as g
    left join mouvements as m
        on m.code_compte = g.code_compte
        and m.id_agence = g.id_agence
        and m.date_fin_mois = g.date_fin_mois
),

avec_ouverture as (
    select *, solde_cloture - (mouvement_debit - mouvement_credit) as solde_ouverture
    from soldes
)

select
    cast(date_fin_mois as date) as date_fin_mois,
    cast(code_compte as text) as code_compte,
    cast(id_agence as text) as id_agence,
    cast(greatest(solde_ouverture, 0) as bigint) as solde_ouverture_debit,
    cast(greatest(-solde_ouverture, 0) as bigint) as solde_ouverture_credit,
    cast(mouvement_debit as bigint) as mouvement_debit,
    cast(mouvement_credit as bigint) as mouvement_credit,
    cast(greatest(solde_cloture, 0) as bigint) as solde_cloture_debit,
    cast(greatest(-solde_cloture, 0) as bigint) as solde_cloture_credit
from avec_ouverture
