-- montant_paye = capital + intérêts + pénalités pour chaque remboursement.
select id_remboursement, montant_paye, part_capital, part_interets, penalites
from {{ ref('fct_remboursements') }}
where montant_paye <> part_capital + part_interets + penalites
