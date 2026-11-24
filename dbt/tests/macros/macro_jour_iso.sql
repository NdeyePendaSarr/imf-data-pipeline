-- jour_iso : 1 = lundi … 7 = dimanche, sur les deux moteurs (BigQuery : pas DAYOFWEEK).
with cas as (
    select cast('2025-02-16' as date) as jour, 7 as attendu  -- dimanche
    union all select cast('2025-02-17' as date), 1             -- lundi
    union all select cast('2025-02-22' as date), 6             -- samedi
)
select jour, attendu, {{ jour_iso('jour') }} as obtenu
from cas
where {{ jour_iso('jour') }} is distinct from attendu
