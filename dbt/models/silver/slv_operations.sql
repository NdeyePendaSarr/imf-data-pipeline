-- Opérations valides, dédoublonnées, canal standardisé (FRAIS_TENUE compris, S15).
-- Lignes de stg_operations sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_operation as text) as id_operation,
    cast(id_compte as text) as id_compte,
    cast(id_agence as text) as id_agence,
    cast(date_operation as date) as date_operation,
    cast(type_operation as text) as type_operation,
    cast(canal as text) as canal,
    cast(montant as bigint) as montant,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_operations') }}
where motif_ecart is null
