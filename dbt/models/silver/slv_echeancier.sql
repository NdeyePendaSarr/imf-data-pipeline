-- Échéancier théorique, dernière version.
-- Lignes de stg_echeancier sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_credit as text) as id_credit,
    cast(num_echeance as smallint) as num_echeance,
    cast(date_echeance as date) as date_echeance,
    cast(capital as bigint) as capital,
    cast(interets as bigint) as interets,
    cast(montant as bigint) as montant,
    cast(date_maj as timestamp) as date_maj,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_echeancier') }}
where motif_ecart is null
