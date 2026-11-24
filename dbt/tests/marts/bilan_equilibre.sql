-- Actif = passif + résultat cumulé à chaque fin de mois (le résultat est une ligne du passif).
-- sum(case when …) : SQL standard (filter (where …) n'existe pas en BigQuery), même résultat.
select
    date_fin_mois,
    sum(case when cote = 'ACTIF' then montant end) as actif,
    sum(case when cote = 'PASSIF' then montant end) as passif_et_resultat
from {{ ref('mart_bilan') }}
group by date_fin_mois
having sum(case when cote = 'ACTIF' then montant end)
    is distinct from sum(case when cote = 'PASSIF' then montant end)
