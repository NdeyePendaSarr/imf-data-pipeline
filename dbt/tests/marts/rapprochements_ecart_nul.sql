-- D9 : gestion = comptabilité au franc près, pour chaque fin de mois, agence et contrôle.
select * from {{ ref('mart_rapprochements') }} where ecart <> 0
