-- Actif = passif + résultat cumulé à chaque fin de mois (le résultat est une ligne du passif).
select
    date_fin_mois,
    sum(montant) filter (where cote = 'ACTIF') as actif,
    sum(montant) filter (where cote = 'PASSIF') as passif_et_resultat
from {{ ref('mart_bilan') }}
group by date_fin_mois
having sum(montant) filter (where cote = 'ACTIF')
    is distinct from sum(montant) filter (where cote = 'PASSIF')
