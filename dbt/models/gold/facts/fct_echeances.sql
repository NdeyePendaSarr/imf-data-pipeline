-- Échéances, une ligne par (crédit, numéro), avec leur couverture au 31/12 de l'exercice (G11).
-- Imputation FIFO cumulée : les paiements (capital + intérêts, pénalités exclues) couvrent les
-- échéances de la plus ancienne à la plus récente. L'échéance k est couverte le premier jour où
-- le cumul payé atteint le cumul dû des échéances 1 à k.
{%- set arrete = "cast('" ~ var('exercice') ~ "-12-31' as date)" %}

with echeances as (
    select
        e.id_credit,
        e.num_echeance,
        e.date_echeance as date_prevue,
        e.capital as capital_du,
        e.interets as interets_dus,
        e.capital + e.interets as montant_du,
        sum(e.capital + e.interets) over (
            partition by e.id_credit order by e.num_echeance
        ) as cumul_du
    from {{ ref('slv_echeancier') }} as e
),

paiements as (
    -- Cumul payé (capital + intérêts) après chaque remboursement de l'exercice.
    select
        id_credit,
        date_remboursement,
        sum(part_capital + part_interets) over (
            partition by id_credit order by date_remboursement, id_remboursement
        ) as cumul_paye
    from {{ ref('slv_remboursements') }}
    where date_remboursement <= {{ arrete }}
),

total_paye as (
    select id_credit, max(cumul_paye) as paye_au_31_12
    from paiements
    group by id_credit
),

couverture as (
    select e.id_credit, e.num_echeance, min(p.date_remboursement) as date_couverture
    from echeances as e
    inner join paiements as p on p.id_credit = e.id_credit and p.cumul_paye >= e.cumul_du
    group by e.id_credit, e.num_echeance
)

select
    e.id_credit,
    e.num_echeance,
    c.id_client,
    cl.id_agence,
    c.code_produit,
    e.date_prevue,
    e.capital_du,
    e.interets_dus,
    e.montant_du,
    -- Part de l'échéance déjà payée au 31/12 : ce qui reste du cumul payé après les échéances
    -- précédentes, borné à 0 et au montant dû.
    cast(least(e.montant_du, greatest(0, coalesce(t.paye_au_31_12, 0) - (e.cumul_du - e.montant_du)))
        as bigint) as montant_impute_au_31_12,
    cv.date_couverture,
    -- Retard : de la date prévue à la couverture, ou au 31/12 si l'échéance n'est pas couverte.
    cast(greatest(0, coalesce(cv.date_couverture, {{ arrete }}) - e.date_prevue) as integer)
        as jours_retard
from echeances as e
inner join {{ ref('slv_credits') }} as c on c.id_credit = e.id_credit
inner join {{ ref('slv_clients') }} as cl on cl.id_client = c.id_client
left join total_paye as t on t.id_credit = e.id_credit
left join couverture as cv on cv.id_credit = e.id_credit and cv.num_echeance = e.num_echeance
