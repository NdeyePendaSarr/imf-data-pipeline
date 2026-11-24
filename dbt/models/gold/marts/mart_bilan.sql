-- Bilan simplifié au niveau de l'IMF (H7), une ligne par rubrique × fin de mois de l'exercice.
--   Soldes calculés sur les mouvements cumulés agrégés de toutes les agences (Σ D − Σ C par
--   compte), jamais en additionnant des soldes d'agence : la banque ou une liaison peut être
--   créditrice dans une agence et débitrice au niveau de l'IMF (G6, D19).
--   Un solde du sens normal du compte va dans sa rubrique ; un solde inversé va dans
--   rubrique_solde_inverse (H8, seed plan_comptes v0.5) : une dette envers les agents ou
--   l'opérateur mobile n'est pas compensée avec la trésorerie.
--   Le résultat cumulé de l'exercice (mart_compte_resultat, H9) est une ligne du passif,
--   négative en cas de perte (pas d'écriture de clôture, D12).
--   Ordre de présentation : actif (A1, A2), puis passif (P1, résultat, P2, P3).

with fins_de_mois as (
    select date as date_fin_mois
    from {{ ref('dim_date') }}
    -- Mois jusqu'au mois de l'arrêté inclus ; le dernier peut être partiel (date_situation).
    where dans_exercice and est_fin_de_mois
        and date_trunc('month', date) <= date_trunc('month', {{ date_arrete() }})
),

comptes as (
    select code_compte, sens_normal, rubrique, rubrique_solde_inverse
    from {{ ref('dim_compte_comptable') }}
    where etat = 'BILAN'
),

mouvements as (
    -- Mouvements du mois par compte, toutes agences confondues.
    select
        e.code_compte,
        (date_trunc('month', e.date_ecriture) + interval '1 month - 1 day')::date as date_fin_mois,
        sum(e.debit - e.credit) as mouvement_net
    from {{ ref('fct_ecritures') }} as e
    inner join comptes as c on c.code_compte = e.code_compte
    group by 1, 2
),

soldes as (
    -- Solde (débit − crédit) de chaque compte à chaque fin de mois, au niveau de l'IMF.
    select
        c.code_compte,
        c.sens_normal,
        c.rubrique,
        c.rubrique_solde_inverse,
        f.date_fin_mois,
        sum(coalesce(m.mouvement_net, 0)) over (
            partition by c.code_compte order by f.date_fin_mois
        ) as solde
    from comptes as c
    cross join fins_de_mois as f
    left join mouvements as m on m.code_compte = c.code_compte and m.date_fin_mois = f.date_fin_mois
),

classes as (
    select
        date_fin_mois,
        solde,
        -- Solde inversé : créditeur pour un compte de sens débit, débiteur pour un compte de sens
        -- crédit. Il va dans rubrique_solde_inverse (un solde inversé sans cette rubrique est
        -- signalé par le test bilan_solde_inverse_sans_rubrique et reste dans sa rubrique).
        case
            when ((sens_normal = 'D' and solde < 0) or (sens_normal = 'C' and solde > 0))
                and rubrique_solde_inverse is not null
                then rubrique_solde_inverse
            else rubrique
        end as rubrique_bilan
    from soldes
),

rubriques as (
    -- Toutes les rubriques possibles du bilan, présentes chaque mois (même à 0).
    select rubrique from comptes
    union
    select rubrique_solde_inverse from comptes where rubrique_solde_inverse is not null
),

postes as (
    -- Montant de chaque rubrique : actif (A…) = Σ (D − C), passif (P…) = Σ (C − D).
    select
        f.date_fin_mois,
        r.rubrique,
        case when r.rubrique like 'A%' then 'ACTIF' else 'PASSIF' end as cote,
        coalesce(sum(case when r.rubrique like 'A%' then c.solde else -c.solde end), 0) as montant
    from rubriques as r
    cross join fins_de_mois as f
    left join classes as c on c.rubrique_bilan = r.rubrique and c.date_fin_mois = f.date_fin_mois
    group by f.date_fin_mois, r.rubrique

    union all

    -- Résultat cumulé de l'exercice, au passif (négatif en cas de perte).
    select f.date_fin_mois, 'RESULTAT_CUMULE', 'PASSIF', coalesce(sum(cr.resultat_cumul), 0)
    from fins_de_mois as f
    left join {{ ref('mart_compte_resultat') }} as cr on cr.date_fin_mois = f.date_fin_mois
    group by f.date_fin_mois
)

select
    cast(p.date_fin_mois as date) as date_fin_mois,
    -- Actif par code de rubrique, puis passif : capitaux propres, résultat, puis dettes.
    -- Tri sur le préfixe (A1, A2, P1…) ; le résultat suit P1 (capitaux propres). Indépendant de la
    -- collation de la base.
    cast(row_number() over (
        partition by p.date_fin_mois
        order by
            p.cote,
            case when p.rubrique = 'RESULTAT_CUMULE' then 'P1' else substr(p.rubrique, 1, 2) end,
            p.rubrique = 'RESULTAT_CUMULE',
            p.rubrique
    ) as integer) as ordre,
    cast(p.cote as text) as cote,
    cast(p.rubrique as text) as rubrique,
    -- Libellé d'affichage (K14, seed de présentation) ; jointure externe : un libellé manquant
    -- est signalé par le test not_null au lieu de faire disparaître la ligne.
    cast(l.libelle as text) as libelle_rubrique,
    cast(p.montant as bigint) as montant,
    cast(least(p.date_fin_mois, {{ date_arrete() }}) as date) as date_situation
from postes as p
left join {{ ref('rubriques_etats') }} as l on l.rubrique = p.rubrique
