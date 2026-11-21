-- Approvisionnements de caisse valides (D18).
-- Lignes de stg_appro_caisse sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_appro as text) as id_appro,
    cast(id_agence as text) as id_agence,
    cast(date_appro as date) as date_appro,
    cast(montant as bigint) as montant,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_appro_caisse') }}
where motif_ecart is null
