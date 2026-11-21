-- Ouvertures valides du 01/01 : capital (VIREMENT) et fonds de caisse (GUICHET).
-- Lignes de stg_ouverture sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_agence as text) as id_agence,
    cast(date_ouverture as date) as date_ouverture,
    cast(canal as text) as canal,
    cast(montant as bigint) as montant,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_ouverture') }}
where motif_ecart is null
