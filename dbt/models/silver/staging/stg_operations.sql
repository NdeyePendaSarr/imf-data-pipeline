-- Opérations des comptes (partitions CSV) : typage sûr, codes standardisés, motif d'écart.
-- FRAIS_TENUE reste une opération (S15).
with source as (
    select * from {{ source('bronze', 'csv_operations') }}
),

typee as (
    select
        trim(id_operation) as id_operation,
        trim(id_compte) as id_compte,
        trim(id_agence) as id_agence,
        {{ vers_date('date_operation') }} as date_operation,
        {{ standardiser('type_operation') }} as type_operation,
        -- « guichet », « Mobile » → GUICHET, MOBILE : corrige FORMAT_CANAL (S5).
        {{ standardiser('canal') }} as canal,
        {{ vers_bigint('montant') }} as montant,
        _id_run,
        _source,
        _num_ligne,
        -- Rang de doublon par identifiant, 1re occurrence gardée (S7).
        row_number() over (partition by trim(id_operation) order by _source, _num_ligne) as rang_doublon
    from source
),

comptes as (
    select id_compte from {{ ref('stg_comptes') }} where motif_ecart is null
),

motifs as (
    select
        typee.*,
        -- Un seul motif par ligne, par ordre de priorité (S6).
        case
            when nullif(id_operation, '') is null or nullif(id_compte, '') is null
                or date_operation is null or nullif(type_operation, '') is null
                or nullif(canal, '') is null or montant is null
                then 'TYPE_INVALIDE'
            when not exists (select 1 from comptes where comptes.id_compte = typee.id_compte)
                then 'ORPHELIN_COMPTE'
            when montant < 0 then 'MONTANT_NEGATIF'
            when not exists (
                select 1 from {{ ref('canaux_autorises') }} as a
                where a.source = 'operations' and a.canal = typee.canal
            ) then 'CANAL_NON_AUTORISE'
        end as motif_regle
    from typee
)

select
    id_operation, id_compte, id_agence, date_operation, type_operation, canal, montant,
    _id_run, _source, _num_ligne, rang_doublon,
    -- Les copies (rang > 1) d'une ligne valide sont des doublons exacts à dédoublonner.
    coalesce(motif_regle, case when rang_doublon > 1 then 'DOUBLON_EXACT' end) as motif_ecart
from motifs
