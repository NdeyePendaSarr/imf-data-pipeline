-- type_datetime et type_taux : heure locale conservée (date_maj à 20:00, sans fuseau) ; taux à
-- 4 décimales conservé exactement.
with cas as (
    select
        cast('2025-05-10 20:00:00' as {{ type_datetime() }}) as horodatage,
        cast(0.1400 as {{ type_taux() }}) as taux
)
select *
from cas
where extract(hour from horodatage) <> 20
    or cast(horodatage as date) <> cast('2025-05-10' as date)
    or taux <> 0.14
    or taux * 10000 <> 1400
