-- KPI du portefeuille (H11), une ligne par jour calendaire de l'exercice × agence × produit.
-- Numérateurs et dénominateurs seulement, aucun ratio stocké (ratios non additifs, recalculés
-- dans Power BI) :
--   PAR 30                 = encours_par30 / encours ;
--   taux de remboursement  = paye_impute_cumule / du_echu_cumule.
-- Par crédit et par jour d, depuis le décaissement jusqu'au 31/12 (un crédit soldé reste compté
-- dans le dû et le payé) :
--   du_echu_cumule     = capital + intérêts des échéances de date prévue ≤ d (fct_echeances) ;
--   paye_impute_cumule = min(cumul payé capital + intérêts jusqu'à d, du_echu_cumule), calculé
--                        par crédit AVANT agrégation (pénalités exclues, FIFO G11) : un paiement
--                        anticipé ne porte pas le taux au-delà de 100 %.
--   encours, encours_par30 (retard > 30 jours), nb_credits_actifs : fct_portefeuille_quotidien.

with jours as (
    select date as jour from {{ ref('dim_date') }} where dans_exercice and date <= {{ date_arrete() }}
),

credits as (
    select c.id_credit, cl.id_agence, c.code_produit, c.date_decaissement
    from {{ ref('dim_credit') }} as c
    inner join {{ ref('dim_client') }} as cl on cl.id_client = c.id_client
),

grille as (
    select c.id_credit, c.id_agence, c.code_produit, j.jour
    from credits as c
    inner join jours as j on j.jour >= c.date_decaissement
),

du_echu as (
    -- Cumul dû : échéances de date prévue ≤ jour (convention « échue » de G11 et de
    -- fct_portefeuille_quotidien). Calcul par comparaison de dates, sans supposer un calendrier
    -- complet.
    select g.id_credit, g.jour, sum(e.capital_du + e.interets_dus) as du_echu_cumule
    from grille as g
    inner join {{ ref('fct_echeances') }} as e on e.id_credit = g.id_credit and e.date_prevue <= g.jour
    group by 1, 2
),

paye as (
    -- Cumul payé (capital + intérêts, pénalités exclues) jusqu'au jour inclus.
    select g.id_credit, g.jour, sum(r.part_capital + r.part_interets) as paye_cumule
    from grille as g
    inner join {{ ref('fct_remboursements') }} as r
        on r.id_credit = g.id_credit and r.date_remboursement <= g.jour
    group by 1, 2
),

credit_jour as (
    select
        g.id_credit,
        g.id_agence,
        g.code_produit,
        g.jour,
        coalesce(d.du_echu_cumule, 0) as du_echu_cumule,
        coalesce(p.paye_cumule, 0) as paye_cumule
    from grille as g
    left join du_echu as d on d.id_credit = g.id_credit and d.jour = g.jour
    left join paye as p on p.id_credit = g.id_credit and p.jour = g.jour
),

par_credit as (
    select
        cj.jour,
        cj.id_agence,
        cj.code_produit,
        cj.du_echu_cumule,
        least(cj.paye_cumule, cj.du_echu_cumule) as paye_impute_cumule,
        coalesce(p.encours, 0) as encours,
        case when p.jours_retard > 30 then p.encours else 0 end as encours_par30,
        case when p.encours > 0 then 1 else 0 end as actif
    from credit_jour as cj
    left join {{ ref('fct_portefeuille_quotidien') }} as p
        on p.id_credit = cj.id_credit and p.date = cj.jour
)

select
    cast(jour as date) as date,
    cast(id_agence as {{ dbt.type_string() }}) as id_agence,
    cast(code_produit as {{ dbt.type_string() }}) as code_produit,
    cast(sum(actif) as integer) as nb_credits_actifs,
    cast(sum(encours) as bigint) as encours,
    cast(sum(encours_par30) as bigint) as encours_par30,
    cast(sum(du_echu_cumule) as bigint) as du_echu_cumule,
    cast(sum(paye_impute_cumule) as bigint) as paye_impute_cumule
from par_credit
group by jour, id_agence, code_produit
