-- Une pièce a au moins deux lignes (un débit et un crédit).
select id_ecriture, count(*) as nb_lignes
from {{ ref('fct_ecritures') }}
group by id_ecriture
having count(*) < 2
