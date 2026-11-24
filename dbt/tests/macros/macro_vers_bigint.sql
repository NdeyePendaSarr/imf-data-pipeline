-- vers_bigint : texte invalide ou vide → NULL ; signes - et + acceptés comme en PostgreSQL.
with cas as (
    select '12a' as texte, cast(null as {{ dbt.type_bigint() }}) as attendu
    union all select '', cast(null as {{ dbt.type_bigint() }})
    union all select '-5', cast(-5 as {{ dbt.type_bigint() }})
    union all select '+7', cast(7 as {{ dbt.type_bigint() }})
    union all select ' 345000 ', cast(345000 as {{ dbt.type_bigint() }})
)
select texte, attendu, {{ vers_bigint('texte') }} as obtenu
from cas
where {{ vers_bigint('texte') }} is distinct from attendu
