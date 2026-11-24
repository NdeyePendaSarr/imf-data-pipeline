-- age_revolu : années révolues. Veille et jour d'anniversaire ; né un 29/02, une année non
-- bissextile : 28/02 → anniversaire pas atteint, 01/03 → atteint (résultat de PostgreSQL age(),
-- sur lequel BigQuery est aligné).
with cas as (
    select cast('2025-06-14' as date) as arrete, cast('1990-06-15' as date) as naissance, 34 as attendu
    union all select cast('2025-06-15' as date), cast('1990-06-15' as date), 35
    union all select cast('2025-02-28' as date), cast('2000-02-29' as date), 24
    union all select cast('2025-03-01' as date), cast('2000-02-29' as date), 25
    union all select cast('2024-02-29' as date), cast('2000-02-29' as date), 24
)
select arrete, naissance, attendu, {{ age_revolu('arrete', 'naissance') }} as obtenu
from cas
where {{ age_revolu('arrete', 'naissance') }} is distinct from attendu
