-- Agences valides (instantané).
-- Lignes de stg_agences sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_agence as {{ dbt.type_string() }}) as id_agence,
    cast(nom as {{ dbt.type_string() }}) as nom,
    cast(ville as {{ dbt.type_string() }}) as ville,
    cast(region as {{ dbt.type_string() }}) as region,
    cast(type_agence as {{ dbt.type_string() }}) as type_agence,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_agences') }}
where motif_ecart is null
