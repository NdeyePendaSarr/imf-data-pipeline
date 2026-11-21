-- Charges valides, dédoublonnées.
-- Lignes de stg_charges sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_charge as text) as id_charge,
    cast(id_agence as text) as id_agence,
    cast(date_charge as date) as date_charge,
    cast(categorie as text) as categorie,
    cast(canal as text) as canal,
    cast(montant as bigint) as montant,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_charges') }}
where motif_ecart is null
