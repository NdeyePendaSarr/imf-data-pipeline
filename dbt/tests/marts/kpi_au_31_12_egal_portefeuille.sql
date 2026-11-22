-- Au 31/12, Σ encours et Σ encours_par30 du mart = fct_portefeuille_quotidien au même jour.
-- La comparaison à la vérité (data/_verite/par30.csv : 1 850 520 623 / 92 511 316) est faite
-- par pytest (tests/test_gold_verite.py) : la vérité n'entre jamais dans l'entrepôt.
with mart as (
    select sum(encours) as encours, sum(encours_par30) as encours_par30
    from {{ ref('mart_kpi_portefeuille') }}
    where date = cast('{{ var("exercice") }}-12-31' as date)
),

portefeuille as (
    select
        sum(encours) as encours,
        sum(encours) filter (where jours_retard > 30) as encours_par30
    from {{ ref('fct_portefeuille_quotidien') }}
    where date = cast('{{ var("exercice") }}-12-31' as date)
)

select * from mart cross join portefeuille as p
where mart.encours is distinct from p.encours or mart.encours_par30 is distinct from p.encours_par30
