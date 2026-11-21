-- Aucune échéance avant le décaissement de son crédit.
select e.id_credit, e.num_echeance, e.date_echeance, c.date_decaissement
from {{ ref('slv_echeancier') }} as e
inner join {{ ref('slv_credits') }} as c on c.id_credit = e.id_credit
where e.date_echeance < c.date_decaissement
