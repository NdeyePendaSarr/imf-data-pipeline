-- Rapprochements gestion ↔ comptabilité (D9, H10), une ligne par fin de mois × agence × contrôle.
--   DEPOTS  : gestion = Σ soldes des comptes clients (fct_solde_compte_mensuel) ;
--             compta  = solde créditeur de DEPOTS_EPARGNE (mart_balance, clôture C − D).
--   CREDITS : gestion = Σ encours du portefeuille à la date calendaire de fin de mois (H1) ;
--             compta  = solde débiteur de CREDITS_SAINS (mart_balance, clôture D − C).
--   ecart = gestion − compta ; attendu : 0 partout (test rapprochements_ecart_nul).
--   Grille complète : chaque fin de mois × chaque agence ayant des clients × chaque contrôle, valeur
--   manquante = 0 (janvier n'a aucun crédit : la ligne CREDITS existe, à 0). Une agence qui aurait
--   un solde sur l'un des deux comptes sans avoir de clients est ajoutée à la grille, pour que rien
--   ne disparaisse ; le test rapprochements_grille_complete contrôle le nombre de lignes.

with fins_de_mois as (
    select date as date_fin_mois
    from {{ ref('dim_date') }}
    -- Mois jusqu'au mois de l'arrêté inclus ; le dernier peut être partiel (date_situation).
    where dans_exercice and est_fin_de_mois
        and date_trunc('month', date) <= date_trunc('month', {{ date_arrete() }})
),

gestion as (
    select date_fin_mois, id_agence, 'DEPOTS' as controle, sum(solde) as valeur
    from {{ ref('fct_solde_compte_mensuel') }}
    group by 1, 2

    union all

    select f.date_fin_mois, p.id_agence, 'CREDITS', sum(p.encours)
    from {{ ref('fct_portefeuille_quotidien') }} as p
    -- Encours à la date de situation (fin de mois, ou date d'arrêté pour le mois en cours).
    inner join fins_de_mois as f on least(f.date_fin_mois, {{ date_arrete() }}) = p.date
    group by 1, 2
),

controles as (
    select 'DEPOTS' as controle
    union all
    select 'CREDITS'
),

agences as (
    select id_agence from {{ ref('dim_client') }}
    union
    select id_agence from {{ ref('mart_balance') }}
    where code_compte in ('DEPOTS_EPARGNE', 'CREDITS_SAINS')
),

compta as (
    select
        date_fin_mois,
        id_agence,
        case when code_compte = 'DEPOTS_EPARGNE' then 'DEPOTS' else 'CREDITS' end as controle,
        sum(case
            when code_compte = 'DEPOTS_EPARGNE' then solde_cloture_credit - solde_cloture_debit
            else solde_cloture_debit - solde_cloture_credit
        end) as valeur
    from {{ ref('mart_balance') }}
    -- Les deux comptes rapprochés sont l'objet même du contrôle D9 (cadrage phase 0).
    where code_compte in ('DEPOTS_EPARGNE', 'CREDITS_SAINS')
    group by 1, 2, 3
)

select
    cast(f.date_fin_mois as date) as date_fin_mois,
    cast(a.id_agence as text) as id_agence,
    cast(k.controle as text) as controle,
    cast(coalesce(g.valeur, 0) as bigint) as valeur_gestion,
    cast(coalesce(c.valeur, 0) as bigint) as valeur_compta,
    cast(coalesce(g.valeur, 0) - coalesce(c.valeur, 0) as bigint) as ecart,
    cast(least(f.date_fin_mois, {{ date_arrete() }}) as date) as date_situation
from fins_de_mois as f
cross join agences as a
cross join controles as k
left join gestion as g
    on g.date_fin_mois = f.date_fin_mois and g.id_agence = a.id_agence and g.controle = k.controle
left join compta as c
    on c.date_fin_mois = f.date_fin_mois and c.id_agence = a.id_agence and c.controle = k.controle
