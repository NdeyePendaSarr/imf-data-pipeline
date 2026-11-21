-- H1 : chaque fin de mois de l'exercice a ses lignes de portefeuille, y compris celles qui
-- tombent un dimanche (31/08/2025 et 30/11/2025 pour l'exercice 2025).
select f.date as fin_de_mois
from {{ ref('dim_date') }} as f
left join {{ ref('fct_portefeuille_quotidien') }} as p on p.date = f.date
where f.dans_exercice and f.est_fin_de_mois and f.date >= (
    select min(date) from {{ ref('fct_portefeuille_quotidien') }}
)
group by f.date
having count(p.id_credit) = 0
