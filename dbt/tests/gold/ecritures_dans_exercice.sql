-- Toutes les écritures sont datées dans l'exercice (var exercice).
select id_ecriture, date_ecriture
from {{ ref('fct_ecritures') }}
where extract(year from date_ecriture) <> {{ var('exercice') }}
