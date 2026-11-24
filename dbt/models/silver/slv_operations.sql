-- Opérations valides, dédoublonnées, canal standardisé (FRAIS_TENUE compris, S15).
-- Lignes de stg_operations sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_operation as {{ dbt.type_string() }}) as id_operation,
    cast(id_compte as {{ dbt.type_string() }}) as id_compte,
    cast(id_agence as {{ dbt.type_string() }}) as id_agence,
    cast(date_operation as date) as date_operation,
    cast(type_operation as {{ dbt.type_string() }}) as type_operation,
    cast(canal as {{ dbt.type_string() }}) as canal,
    cast(montant as bigint) as montant,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_operations') }}
where motif_ecart is null
