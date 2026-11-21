-- Partie double : Σ débit = Σ crédit pour chaque pièce, et sur l'ensemble des écritures.
select id_ecriture, sum(debit) as total_debit, sum(credit) as total_credit
from {{ ref('fct_ecritures') }}
group by id_ecriture
having sum(debit) <> sum(credit)

union all

select 'TOTAL', sum(debit), sum(credit)
from {{ ref('fct_ecritures') }}
having sum(debit) <> sum(credit)
