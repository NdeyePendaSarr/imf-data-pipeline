-- Crédits, dernière version. statut renommé statut_au_31_12 (S9).
-- Lignes de stg_credits sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_credit as {{ dbt.type_string() }}) as id_credit,
    cast(id_client as {{ dbt.type_string() }}) as id_client,
    cast(id_compte_epargne as {{ dbt.type_string() }}) as id_compte_epargne,
    cast(code_produit as {{ dbt.type_string() }}) as code_produit,
    cast(date_decaissement as date) as date_decaissement,
    cast(montant_accorde as bigint) as montant_accorde,
    cast(frais_dossier as bigint) as frais_dossier,
    cast(duree_mois as smallint) as duree_mois,
    cast(taux_annuel as {{ type_taux() }}) as taux_annuel,
    cast(statut as {{ dbt.type_string() }}) as statut_au_31_12,
    cast(date_maj as {{ type_datetime() }}) as date_maj,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_credits') }}
where motif_ecart is null
