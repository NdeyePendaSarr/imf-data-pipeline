-- Charges valides, dédoublonnées.
-- Lignes de stg_charges sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_charge as {{ dbt.type_string() }}) as id_charge,
    cast(id_agence as {{ dbt.type_string() }}) as id_agence,
    cast(date_charge as date) as date_charge,
    cast(categorie as {{ dbt.type_string() }}) as categorie,
    cast(canal as {{ dbt.type_string() }}) as canal,
    cast(montant as bigint) as montant,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_charges') }}
where motif_ecart is null
