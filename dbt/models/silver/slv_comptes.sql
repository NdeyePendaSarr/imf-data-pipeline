-- Comptes, dernière version.
-- Lignes de stg_comptes sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_compte as text) as id_compte,
    cast(id_client as text) as id_client,
    cast(type_compte as text) as type_compte,
    cast(date_ouverture as date) as date_ouverture,
    cast(statut as text) as statut,
    cast(date_maj as timestamp) as date_maj,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_comptes') }}
where motif_ecart is null
