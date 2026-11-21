-- 0 < encours ≤ montant accordé pour chaque crédit et chaque jour.
select p.id_credit, p.date, p.encours, c.montant_accorde
from {{ ref('fct_portefeuille_quotidien') }} as p
inner join {{ ref('dim_credit') }} as c on c.id_credit = p.id_credit
where p.encours <= 0 or p.encours > c.montant_accorde
