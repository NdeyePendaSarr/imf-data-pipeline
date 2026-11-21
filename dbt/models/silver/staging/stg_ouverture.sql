-- Ouvertures du 01/01 (instantané CSV) : capital en banque (VIREMENT) et fonds de caisse (GUICHET).
-- Clé métier : (agence, canal).
with source as (
    select * from {{ source('bronze', 'csv_ouverture') }}
),

typee as (
    select
        trim(id_agence) as id_agence,
        {{ vers_date('date_ouverture') }} as date_ouverture,
        {{ standardiser('canal') }} as canal,
        {{ vers_bigint('montant') }} as montant,
        _id_run,
        _source,
        _num_ligne,
        row_number() over (
            partition by trim(id_agence), {{ standardiser('canal') }} order by _source, _num_ligne
        ) as rang_doublon
    from source
),

motifs as (
    select
        typee.*,
        -- Un seul motif par ligne, par ordre de priorité (S6).
        case
            when nullif(id_agence, '') is null or date_ouverture is null or montant is null
                then 'TYPE_INVALIDE'
            when montant < 0 then 'MONTANT_NEGATIF'
            when not exists (
                select 1 from {{ ref('canaux_autorises') }} as a
                where a.source = 'ouverture' and a.canal = typee.canal
            ) then 'CANAL_NON_AUTORISE'
        end as motif_regle
    from typee
)

select
    id_agence, date_ouverture, canal, montant, _id_run, _source, _num_ligne, rang_doublon,
    -- Identifiant d'écart : la clé (agence, canal) en une seule colonne.
    id_agence || '|' || canal as id_ligne,
    coalesce(motif_regle, case when rang_doublon > 1 then 'DOUBLON_EXACT' end) as motif_ecart
from motifs
