-- Événements qui ne peuvent pas être comptabilisés (G3), un motif par événement :
--   TYPE_SANS_REGLE        aucune règle mvp de mapping_comptable pour (type_evenement, source) ;
--   CANAL_SANS_TRESORERIE  une règle @TRESORERIE mais un canal absent de mapping_canal_tresorerie ;
--   COMPTE_HORS_PLAN       un compte (règle ou trésorerie résolue) absent du plan, ou hors MVP.
-- Seules les règles mvp = true comptent. Attendu : aucune ligne (test dbt).

with evenements as (
    select distinct type_evenement, source_table, source_id, canal
    from {{ ref('int_evenements_comptables') }}
),

regles as (
    select type_evenement, source, code_compte
    from {{ ref('mapping_comptable') }}
    where mvp
),

plan_mvp as (
    select code_compte from {{ ref('plan_comptes') }} where mvp
),

lignes as (
    -- Comptes que chaque événement mouvementerait, @TRESORERIE résolu par le canal.
    select
        e.type_evenement,
        e.source_table,
        e.source_id,
        r.code_compte as code_regle,
        case when r.code_compte = '@TRESORERIE' then t.code_compte else r.code_compte end
            as code_compte
    from evenements as e
    inner join regles as r on r.type_evenement = e.type_evenement and r.source = e.source_table
    left join {{ ref('mapping_canal_tresorerie') }} as t on t.canal = e.canal
),

motifs as (
    select
        e.type_evenement,
        e.source_table,
        e.source_id,
        case
            when not exists (
                select 1 from regles as r
                where r.type_evenement = e.type_evenement and r.source = e.source_table
            ) then 'TYPE_SANS_REGLE'
            when exists (
                select 1 from lignes as l
                where l.source_table = e.source_table and l.source_id = e.source_id
                    and l.type_evenement = e.type_evenement
                    and l.code_regle = '@TRESORERIE' and l.code_compte is null
            ) then 'CANAL_SANS_TRESORERIE'
            when exists (
                select 1 from lignes as l
                where l.source_table = e.source_table and l.source_id = e.source_id
                    and l.type_evenement = e.type_evenement
                    and l.code_compte not in (select code_compte from plan_mvp)
            ) then 'COMPTE_HORS_PLAN'
        end as motif
    from evenements as e
)

select
    cast(type_evenement as text) as type_evenement,
    cast(source_table as text) as source_table,
    cast(source_id as text) as source_id,
    cast(motif as text) as motif
from motifs
where motif is not null
