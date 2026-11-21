-- Clients, dernière version ; NULL acceptés sur date_naissance et secteur_activite.
-- Lignes de stg_clients sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_client as text) as id_client,
    cast(id_agence as text) as id_agence,
    cast(prenom as text) as prenom,
    cast(nom as text) as nom,
    cast(sexe as text) as sexe,
    cast(date_naissance as date) as date_naissance,
    cast(secteur_activite as text) as secteur_activite,
    cast(date_adhesion as date) as date_adhesion,
    cast(date_maj as timestamp) as date_maj,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_clients') }}
where motif_ecart is null
