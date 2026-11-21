-- Agences valides (instantané).
-- Lignes de stg_agences sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_agence as text) as id_agence,
    cast(nom as text) as nom,
    cast(ville as text) as ville,
    cast(region as text) as region,
    cast(type_agence as text) as type_agence,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_agences') }}
where motif_ecart is null
