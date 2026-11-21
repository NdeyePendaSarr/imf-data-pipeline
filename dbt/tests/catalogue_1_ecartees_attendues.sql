-- Catalogue (1) : chaque ligne REJETER / DEDOUBLONNER du catalogue est dans slv_lignes_ecartees,
-- même table, même identifiant, même nature ; pour un doublon, autant de lignes que de copies.
with attendu as (
    select
        table_source,
        id_ligne,
        nature,
        case when nature = 'DOUBLON_EXACT' then nombre else 1 end as nb_attendu
    from {{ ref('stg_catalogue_anomalies') }}
    where traitement_attendu in ('REJETER', 'DEDOUBLONNER')
),

obtenu as (
    select table_source, id_ligne, motif_ecart as nature, count(*) as nb_obtenu
    from {{ ref('slv_lignes_ecartees') }}
    group by table_source, id_ligne, motif_ecart
)

select attendu.*, obtenu.nb_obtenu
from attendu
left join obtenu using (table_source, id_ligne, nature)
where obtenu.nb_obtenu is distinct from attendu.nb_attendu
