-- Agences (instantané CSV) : texte nettoyé, type d'agence standardisé.
with source as (
    select * from {{ source('bronze', 'csv_agences') }}
),

typee as (
    select
        trim(id_agence) as id_agence,
        trim(nom) as nom,
        trim(ville) as ville,
        trim(region) as region,
        {{ standardiser('type_agence') }} as type_agence,
        _id_run,
        _source,
        _num_ligne,
        -- Rang de doublon par identifiant : la 1re occurrence (fichier, ligne) est gardée (S7).
        row_number() over (partition by trim(id_agence) order by _source, _num_ligne) as rang_doublon
    from source
)

select
    *,
    case
        when nullif(id_agence, '') is null or nullif(type_agence, '') is null then 'TYPE_INVALIDE'
        when rang_doublon > 1 then 'DOUBLON_EXACT'
    end as motif_ecart
from typee
