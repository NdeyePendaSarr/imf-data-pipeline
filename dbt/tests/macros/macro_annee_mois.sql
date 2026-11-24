-- annee_mois : AAAA-MM, mois sur deux chiffres.
with cas as (
    select cast('2025-01-01' as date) as jour, '2025-01' as attendu
    union all select cast('2025-12-31' as date), '2025-12'
    union all select cast('2027-02-28' as date), '2027-02'
)
select jour, attendu, {{ annee_mois('jour') }} as obtenu
from cas
where {{ annee_mois('jour') }} is distinct from attendu
