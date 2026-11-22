-- Grille complète des rapprochements : 12 fins de mois × agences ayant des clients × 2 contrôles
-- (DEPOTS, CREDITS), sans ligne en plus ni en moins (120 lignes pour 5 agences).
with attendu as (
    select
        (select count(*) from {{ ref('dim_date') }} where dans_exercice and est_fin_de_mois)
        * (select count(distinct id_agence) from {{ ref('dim_client') }})
        * 2 as nb
),

obtenu as (
    select count(*) as nb from {{ ref('mart_rapprochements') }}
)

select attendu.nb as attendu, obtenu.nb as obtenu
from attendu cross join obtenu
where attendu.nb <> obtenu.nb
