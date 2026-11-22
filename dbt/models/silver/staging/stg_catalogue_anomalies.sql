-- Catalogue des anomalies (métadonnée de test) : sert uniquement aux tests de catalogue.
select
    {{ standardiser('nature') }} as nature,
    trim("table") as table_source,
    trim(id_ligne) as id_ligne,
    {{ vers_bigint('nombre') }} as nombre,
    {{ standardiser('traitement_attendu') }} as traitement_attendu,
    -- Date de l'événement visé (phase 7) : restreint les tests du catalogue à une date d'arrêté.
    {{ vers_date('date_ligne') }} as date_ligne,
    _id_run,
    _source,
    _num_ligne
from {{ source('bronze', 'meta_catalogue_anomalies') }}
