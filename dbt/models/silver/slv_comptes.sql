-- Comptes, dernière version.
-- Lignes de stg_comptes sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_compte as {{ dbt.type_string() }}) as id_compte,
    cast(id_client as {{ dbt.type_string() }}) as id_client,
    cast(type_compte as {{ dbt.type_string() }}) as type_compte,
    cast(date_ouverture as date) as date_ouverture,
    cast(statut as {{ dbt.type_string() }}) as statut,
    cast(date_maj as {{ type_datetime() }}) as date_maj,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_comptes') }}
where motif_ecart is null
