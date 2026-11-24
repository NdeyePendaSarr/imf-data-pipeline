-- vers_date : date inexistante, texte vide ou mal formé → NULL ; date valide (29/02 bissextile).
with cas as (
    select '2025-02-31' as texte, cast(null as date) as attendu
    union all select '', cast(null as date)
    union all select '2025-2-3', cast(null as date)
    union all select '2024-02-29', cast('2024-02-29' as date)
    union all select ' 2025-12-31 ', cast('2025-12-31' as date)
)
select texte, attendu, {{ vers_date('texte') }} as obtenu
from cas
where {{ vers_date('texte') }} is distinct from attendu
