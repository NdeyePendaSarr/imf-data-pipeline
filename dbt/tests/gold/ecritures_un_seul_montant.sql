-- Chaque ligne a exactement un montant strictement positif : au débit ou au crédit.
select id_ecriture, num_ligne, debit, credit
from {{ ref('fct_ecritures') }}
where not ((debit > 0 and credit = 0) or (credit > 0 and debit = 0))
