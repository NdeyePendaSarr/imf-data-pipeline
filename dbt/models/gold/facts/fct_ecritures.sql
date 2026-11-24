-- Écritures comptables en partie double (une ligne d'écriture par ligne), générées par
-- jointure des événements avec les règles du mapping : aucune logique propre à un type
-- d'événement dans ce modèle (pas de CASE sur type_evenement).
--   Pièce : id_ecriture = source_table:source_id:type_evenement (G4).
--   @TRESORERIE : compte de trésorerie du canal (mapping_canal_tresorerie).
--   Journal (D15) : la plus forte priorité parmi le journal imposé par le type (journaux.type_evenement),
--   le journal du canal de la ligne @TRESORERIE et OD.
-- Les événements rejetés (int_evenements_rejetes) et les lignes à montant 0 sont exclus.

with evenements as (
    select e.*
    from {{ ref('int_evenements_comptables') }} as e
    -- Aucun événement postérieur à la date d'arrêté.
    where e.date_evenement <= {{ date_arrete() }}
    and not exists (
        select 1 from {{ ref('int_evenements_rejetes') }} as r
        where r.source_table = e.source_table
            and r.source_id = e.source_id
            and r.type_evenement = e.type_evenement
    )
),

lignes as (
    select
        e.source_table || ':' || e.source_id || ':' || e.type_evenement as id_ecriture,
        r.num_ligne,
        e.date_evenement as date_ecriture,
        e.id_agence,
        coalesce(t.code_compte, r.code_compte) as code_compte,
        -- Journal du canal, porté seulement par la ligne @TRESORERIE.
        t.code_journal as journal_canal,
        case when r.sens = 'D' then e.montant else 0 end as debit,
        case when r.sens = 'C' then e.montant else 0 end as credit,
        e.type_evenement,
        e.source_table,
        e.source_id
    from evenements as e
    inner join {{ ref('mapping_comptable') }} as r
        on r.type_evenement = e.type_evenement
        and r.source = e.source_table
        and r.champ_montant = e.champ_montant
        and r.mvp
    left join {{ ref('mapping_canal_tresorerie') }} as t
        on r.code_compte = '@TRESORERIE' and t.canal = e.canal
    where e.montant <> 0
),

candidats_journal as (
    -- 1 : journal imposé par le type d'événement (OUV, VIR).
    select l.id_ecriture, j.code_journal, j.priorite
    from (select distinct id_ecriture, type_evenement from lignes) as l
    inner join {{ ref('journaux') }} as j on j.type_evenement = l.type_evenement

    union all

    -- 2 : journal du canal de trésorerie (CAI, AGT, MOB, BQ ; PRELEVEMENT → OD).
    select l.id_ecriture, j.code_journal, j.priorite
    from lignes as l
    inner join {{ ref('journaux') }} as j on j.code_journal = l.journal_canal

    union all

    -- 3 : opérations diverses, pour toute pièce.
    select distinct l.id_ecriture, j.code_journal, j.priorite
    from lignes as l
    cross join {{ ref('journaux') }} as j
    where j.code_journal = 'OD'
),

journal_piece as (
    -- Premier journal candidat de chaque pièce (priorité, puis code) : row_number() = 1 en
    -- sous-requête, SQL standard (distinct on n'existe qu'en PostgreSQL, L6).
    select id_ecriture, code_journal
    from (
        select
            id_ecriture,
            code_journal,
            row_number() over (
                partition by id_ecriture order by priorite, code_journal
            ) as rang
        from candidats_journal
    ) as classes
    where rang = 1
)

select
    cast(l.id_ecriture as {{ dbt.type_string() }}) as id_ecriture,
    cast(l.num_ligne as integer) as num_ligne,
    cast(l.date_ecriture as date) as date_ecriture,
    cast(j.code_journal as {{ dbt.type_string() }}) as code_journal,
    cast(l.id_agence as {{ dbt.type_string() }}) as id_agence,
    cast(l.code_compte as {{ dbt.type_string() }}) as code_compte,
    cast(l.debit as bigint) as debit,
    cast(l.credit as bigint) as credit,
    cast(l.type_evenement as {{ dbt.type_string() }}) as type_evenement,
    cast(l.source_table as {{ dbt.type_string() }}) as source_table,
    cast(l.source_id as {{ dbt.type_string() }}) as source_id,
    cast('{{ var("version_mapping") }}' as {{ dbt.type_string() }}) as version_mapping
from lignes as l
inner join journal_piece as j on j.id_ecriture = l.id_ecriture
