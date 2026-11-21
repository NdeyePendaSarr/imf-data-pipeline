-- Approvisionnements des caisses (partitions CSV, D18) : typage sûr et motif d'écart.
with source as (
    select * from {{ source('bronze', 'csv_appro_caisse') }}
),

typee as (
    select
        trim(id_appro) as id_appro,
        trim(id_agence) as id_agence,
        {{ vers_date('date_appro') }} as date_appro,
        {{ vers_bigint('montant') }} as montant,
        _id_run,
        _source,
        _num_ligne,
        row_number() over (partition by trim(id_appro) order by _source, _num_ligne) as rang_doublon
    from source
),

motifs as (
    select
        typee.*,
        case
            when nullif(id_appro, '') is null or nullif(id_agence, '') is null
                or date_appro is null or montant is null
                then 'TYPE_INVALIDE'
            when montant < 0 then 'MONTANT_NEGATIF'
        end as motif_regle
    from typee
)

select
    id_appro, id_agence, date_appro, montant, _id_run, _source, _num_ligne, rang_doublon,
    coalesce(motif_regle, case when rang_doublon > 1 then 'DOUBLON_EXACT' end) as motif_ecart
from motifs
