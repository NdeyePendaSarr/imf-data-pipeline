-- Portefeuille quotidien (G11, H1) : un crédit × un jour calendaire de l'exercice, du décaissement
-- jusqu'au solde du crédit (encours > 0) ou au 31/12. Un encours est un stock et le retard se
-- compte en jours calendaires : les fins de mois du dimanche (31/08, 30/11) ont leur ligne.
-- est_jour_ouvre (lundi à samedi) permet de filtrer les jours d'activité. À chaque jour d :
--   encours      = montant accordé − capital remboursé jusqu'à d inclus ;
--   jours_retard = d − date prévue de la plus ancienne échéance échue non couverte à d (0 sinon),
--                  même imputation FIFO cumulée que fct_echeances (pénalités exclues) ;
--   tranche_retard : 0, 1-30, 31-90, 91-180, >180. PAR 30 = encours des crédits à plus de 30 jours.

with jours as (
    select date as jour, est_jour_ouvre
    from {{ ref('dim_date') }}
    where dans_exercice and date <= {{ date_arrete() }}
),

credits as (
    select c.id_credit, c.id_client, cl.id_agence, c.code_produit, c.date_decaissement, c.montant_accorde
    from {{ ref('dim_credit') }} as c
    inner join {{ ref('dim_client') }} as cl on cl.id_client = c.id_client
),

paiements_par_jour as (
    select id_credit, date_remboursement, sum(part_capital) as capital, sum(part_capital + part_interets) as paye
    from {{ ref('slv_remboursements') }}
    group by id_credit, date_remboursement
),

cumuls as (
    -- Cumuls après chaque jour de paiement ; valides jusqu'au jour de paiement suivant exclu.
    select
        id_credit,
        date_remboursement as depuis,
        coalesce(lead(date_remboursement) over (partition by id_credit order by date_remboursement), date '9999-12-31') as jusqu_a,
        sum(capital) over (partition by id_credit order by date_remboursement) as capital_rembourse,
        sum(paye) over (partition by id_credit order by date_remboursement) as cumul_paye
    from paiements_par_jour
),

echeances as (
    select
        id_credit,
        date_echeance,
        sum(capital + interets) over (partition by id_credit order by num_echeance) as cumul_du
    from {{ ref('slv_echeancier') }}
),

credit_jour as (
    select
        c.id_credit, c.id_client, c.id_agence, c.code_produit, c.montant_accorde,
        j.jour,
        j.est_jour_ouvre,
        coalesce(cu.capital_rembourse, 0) as capital_rembourse,
        coalesce(cu.cumul_paye, 0) as cumul_paye
    from credits as c
    inner join jours as j on j.jour >= c.date_decaissement
    left join cumuls as cu
        on cu.id_credit = c.id_credit and j.jour >= cu.depuis and j.jour < cu.jusqu_a
),

retards as (
    -- Plus ancienne échéance échue (date prévue ≤ d, même convention que mart_kpi_portefeuille,
    -- H11) et non couverte par le cumul payé à d. Une échéance prévue le jour d et impayée donne
    -- 0 jour de retard : inclure le jour d ne change ni le retard ni le PAR 30.
    select
        cj.id_credit,
        cj.jour,
        min(e.date_echeance) as plus_ancienne_impayee
    from credit_jour as cj
    inner join echeances as e
        on e.id_credit = cj.id_credit and e.date_echeance <= cj.jour and e.cumul_du > cj.cumul_paye
    group by cj.id_credit, cj.jour
),

portefeuille as (
    select
        cj.jour,
        cj.est_jour_ouvre,
        cj.id_credit,
        cj.id_client,
        cj.id_agence,
        cj.code_produit,
        cj.montant_accorde - cj.capital_rembourse as encours,
        coalesce(cj.jour - r.plus_ancienne_impayee, 0) as jours_retard
    from credit_jour as cj
    left join retards as r on r.id_credit = cj.id_credit and r.jour = cj.jour
)

select
    cast(jour as date) as date,
    cast(est_jour_ouvre as boolean) as est_jour_ouvre,
    cast(id_credit as text) as id_credit,
    cast(id_client as text) as id_client,
    cast(id_agence as text) as id_agence,
    cast(code_produit as text) as code_produit,
    cast(encours as bigint) as encours,
    cast(jours_retard as integer) as jours_retard,
    cast(case
        when jours_retard = 0 then '0'
        when jours_retard <= 30 then '1-30'
        when jours_retard <= 90 then '31-90'
        when jours_retard <= 180 then '91-180'
        else '>180'
    end as text) as tranche_retard
from portefeuille
where encours > 0
