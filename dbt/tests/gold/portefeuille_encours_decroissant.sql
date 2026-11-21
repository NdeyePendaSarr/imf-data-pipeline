-- L'encours d'un crédit ne remonte jamais d'un jour au suivant (aucun nouveau tirage).
with suivi as (
    select
        id_credit,
        date,
        encours,
        lag(encours) over (partition by id_credit order by date) as encours_veille
    from {{ ref('fct_portefeuille_quotidien') }}
)

select * from suivi where encours > encours_veille
