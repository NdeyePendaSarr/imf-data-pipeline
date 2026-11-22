-- Compte de résultat (H9), une ligne par rubrique × fin de mois de l'exercice : montant du mois et
-- cumul depuis le 01/01. Aucune écriture de clôture : le résultat est calculé.
--   type_rubrique est déduit de la nature des comptes de la rubrique (PRODUITS, CHARGES, ou MIXTE
--   pour R5_COUT_DU_RISQUE, G15), sans liste de codes en dur.
--   montant_* : dans le sens de la rubrique (produits : crédit − débit ; charges : débit − crédit ;
--   mixte : net en produit).
--   resultat_* : contribution au résultat, crédit − débit ; résultat = Σ resultat_* = produits − charges.
--   Le cumul à fin m alimente le bilan à fin m (phase 6, lot C).
--   Densification : toute rubrique mouvementée dans l'exercice a une ligne chaque mois.

with fins_de_mois as (
    select date as date_fin_mois
    from {{ ref('dim_date') }}
    -- Mois jusqu'au mois de l'arrêté inclus ; le dernier peut être partiel (date_situation).
    where dans_exercice and est_fin_de_mois
        and date_trunc('month', date) <= date_trunc('month', {{ date_arrete() }})
),

comptes as (
    select code_compte, rubrique, nature
    from {{ ref('dim_compte_comptable') }}
    where etat = 'CR'
),

types as (
    select
        rubrique,
        case
            when bool_and(nature = 'PRODUIT') then 'PRODUITS'
            when bool_and(nature = 'CHARGE') then 'CHARGES'
            else 'MIXTE'
        end as type_rubrique
    from comptes
    group by rubrique
),

mouvements as (
    select
        c.rubrique,
        (date_trunc('month', e.date_ecriture) + interval '1 month - 1 day')::date as date_fin_mois,
        sum(e.credit - e.debit) as resultat
    from {{ ref('fct_ecritures') }} as e
    inner join comptes as c on c.code_compte = e.code_compte
    group by 1, 2
),

grille as (
    select r.rubrique, f.date_fin_mois
    from (select distinct rubrique from mouvements) as r
    cross join fins_de_mois as f
),

mensuel as (
    select
        g.date_fin_mois,
        g.rubrique,
        t.type_rubrique,
        coalesce(m.resultat, 0) as resultat_mois,
        sum(coalesce(m.resultat, 0)) over (partition by g.rubrique order by g.date_fin_mois)
            as resultat_cumul
    from grille as g
    inner join types as t on t.rubrique = g.rubrique
    left join mouvements as m on m.rubrique = g.rubrique and m.date_fin_mois = g.date_fin_mois
)

select
    cast(date_fin_mois as date) as date_fin_mois,
    cast(rubrique as text) as rubrique,
    cast(type_rubrique as text) as type_rubrique,
    cast(case when type_rubrique = 'CHARGES' then -resultat_mois else resultat_mois end as bigint)
        as montant_mois,
    cast(case when type_rubrique = 'CHARGES' then -resultat_cumul else resultat_cumul end as bigint)
        as montant_cumul,
    cast(resultat_mois as bigint) as resultat_mois,
    cast(resultat_cumul as bigint) as resultat_cumul,
    cast(least(date_fin_mois, {{ date_arrete() }}) as date) as date_situation
from mensuel
