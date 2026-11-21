-- Aucun remboursement valide avant le décaissement de son crédit.
select r.id_remboursement, r.date_remboursement, c.date_decaissement
from {{ ref('slv_remboursements') }} as r
inner join {{ ref('slv_credits') }} as c on c.id_credit = r.id_credit
where r.date_remboursement < c.date_decaissement
