-- Charges de fonctionnement (partitions CSV) : typage sûr, codes standardisés, motif d'écart.
with source as (
    select * from {{ source('bronze', 'csv_charges') }}
),

typee as (
    select
        trim(id_charge) as id_charge,
        trim(id_agence) as id_agence,
        {{ vers_date('date_charge') }} as date_charge,
        {{ standardiser('categorie') }} as categorie,
        {{ standardiser('canal') }} as canal,
        {{ vers_bigint('montant') }} as montant,
        _id_run,
        _source,
        _num_ligne,
        row_number() over (partition by trim(id_charge) order by _source, _num_ligne) as rang_doublon
    from source
),

motifs as (
    select
        typee.*,
        case
            when nullif(id_charge, '') is null or nullif(id_agence, '') is null
                or date_charge is null or nullif(categorie, '') is null
                or nullif(canal, '') is null or montant is null
                then 'TYPE_INVALIDE'
            when montant < 0 then 'MONTANT_NEGATIF'
            -- Une charge ne se paie que par virement ou en espèces (PRELEVEMENT refusé).
            when not exists (
                select 1 from {{ ref('canaux_autorises') }} as a
                where a.source = 'charges' and a.canal = typee.canal
            ) then 'CANAL_NON_AUTORISE'
        end as motif_regle
    from typee
)

select
    id_charge, id_agence, date_charge, categorie, canal, montant,
    _id_run, _source, _num_ligne, rang_doublon,
    coalesce(motif_regle, case when rang_doublon > 1 then 'DOUBLON_EXACT' end) as motif_ecart
from motifs
