-- Ouvertures valides du 01/01 : capital (VIREMENT) et fonds de caisse (GUICHET).
-- Lignes de stg_ouverture sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_agence as {{ dbt.type_string() }}) as id_agence,
    cast(date_ouverture as date) as date_ouverture,
    cast(canal as {{ dbt.type_string() }}) as canal,
    cast(montant as bigint) as montant,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_ouverture') }}
where motif_ecart is null
