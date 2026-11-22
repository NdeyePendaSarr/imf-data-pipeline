-- Remboursements, une ligne par remboursement, avec les axes du crédit (client, agence, produit).
select
    r.id_remboursement,
    r.id_credit,
    c.id_client,
    cl.id_agence,
    c.code_produit,
    r.date_remboursement,
    r.canal,
    r.montant_paye,
    r.part_capital,
    r.part_interets,
    r.penalites
from {{ ref('slv_remboursements') }} as r
inner join {{ ref('slv_credits') }} as c on c.id_credit = r.id_credit
inner join {{ ref('slv_clients') }} as cl on cl.id_client = c.id_client
where r.date_remboursement <= {{ date_arrete() }}
