-- Clients, dernière version ; NULL acceptés sur date_naissance et secteur_activite.
-- Lignes de stg_clients sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_client as {{ dbt.type_string() }}) as id_client,
    cast(id_agence as {{ dbt.type_string() }}) as id_agence,
    cast(prenom as {{ dbt.type_string() }}) as prenom,
    cast(nom as {{ dbt.type_string() }}) as nom,
    cast(sexe as {{ dbt.type_string() }}) as sexe,
    cast(date_naissance as date) as date_naissance,
    cast(secteur_activite as {{ dbt.type_string() }}) as secteur_activite,
    cast(date_adhesion as date) as date_adhesion,
    cast(date_maj as {{ type_datetime() }}) as date_maj,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_clients') }}
where motif_ecart is null
