-- À la date d'arrêté, Σ encours et Σ encours_par30 du mart = fct_portefeuille_quotidien au même
-- jour. Garde : échec si le mart n'a rien (NULL) alors que le portefeuille n'est pas vide à ce
-- jour (la comparaison NULL = NULL passerait sinon à vide).
-- La comparaison à la vérité (data/_verite/par30.csv) est faite par pytest.
with mart as (
    select sum(encours) as encours, sum(encours_par30) as encours_par30
    from {{ ref('mart_kpi_portefeuille') }}
    where date = {{ date_arrete() }}
),

portefeuille as (
    select
        count(*) as nb_lignes,
        sum(encours) as encours,
        -- sum(case when …) : SQL standard (filter (where …) n'existe pas en BigQuery).
        sum(case when jours_retard > 30 then encours end) as encours_par30
    from {{ ref('fct_portefeuille_quotidien') }}
    where date = {{ date_arrete() }}
)

select * from mart cross join portefeuille as p
where (p.nb_lignes > 0 and mart.encours is null)
    or mart.encours is distinct from p.encours
    or coalesce(mart.encours_par30, 0) <> coalesce(p.encours_par30, 0)
