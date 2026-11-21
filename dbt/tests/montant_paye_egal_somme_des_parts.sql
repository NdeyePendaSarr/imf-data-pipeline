-- Chaque remboursement valide : montant_paye = part_capital + part_interets + penalites.
select id_remboursement, montant_paye, part_capital, part_interets, penalites
from {{ ref('slv_remboursements') }}
where montant_paye <> part_capital + part_interets + penalites
