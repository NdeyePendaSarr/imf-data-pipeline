-- Une pièce n'a qu'un journal (D15).
select id_ecriture, count(distinct code_journal) as nb_journaux
from {{ ref('fct_ecritures') }}
group by id_ecriture
having count(distinct code_journal) <> 1
