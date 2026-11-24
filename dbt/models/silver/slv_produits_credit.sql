-- Produits de crédit, dernière version.
-- Lignes de stg_produits_credit sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(code_produit as {{ dbt.type_string() }}) as code_produit,
    cast(libelle as {{ dbt.type_string() }}) as libelle,
    cast(taux_annuel as {{ type_taux() }}) as taux_annuel,
    cast(taux_frais_dossier as {{ type_taux() }}) as taux_frais_dossier,
    cast(duree_min_mois as smallint) as duree_min_mois,
    cast(duree_max_mois as smallint) as duree_max_mois,
    cast(date_maj as {{ type_datetime() }}) as date_maj,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_produits_credit') }}
where motif_ecart is null
