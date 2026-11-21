-- Complétude : nombre d'événements = nombre de pièces + nombre de rejets.
with comptes as (
    select
        (select count(*) from (
            select distinct source_table, source_id, type_evenement
            from {{ ref('int_evenements_comptables') }}
        ) as e) as nb_evenements,
        (select count(distinct id_ecriture) from {{ ref('fct_ecritures') }}) as nb_pieces,
        (select count(*) from {{ ref('int_evenements_rejetes') }}) as nb_rejets
)

select * from comptes where nb_evenements <> nb_pieces + nb_rejets
