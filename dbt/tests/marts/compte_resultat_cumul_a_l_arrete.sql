-- Cumul du dernier mois présent dans le compte de résultat (mois de l'arrêté) = Σ produits −
-- Σ charges de fct_ecritures jusqu'à la date d'arrêté (produits : C − D ; charges : D − C).
with ecritures as (
    select
        sum(case when c.nature = 'PRODUIT' then e.credit - e.debit else 0 end)
            - sum(case when c.nature = 'CHARGE' then e.debit - e.credit else 0 end) as resultat
    from {{ ref('fct_ecritures') }} as e
    inner join {{ ref('dim_compte_comptable') }} as c on c.code_compte = e.code_compte
    where e.date_ecriture <= {{ date_arrete() }}
),

compte_resultat as (
    select coalesce(sum(resultat_cumul), 0) as resultat
    from {{ ref('mart_compte_resultat') }}
    where date_fin_mois = (select max(date_fin_mois) from {{ ref('mart_compte_resultat') }})
)

select ecritures.resultat as ecritures, compte_resultat.resultat as compte_resultat
from ecritures cross join compte_resultat
where coalesce(ecritures.resultat, 0) <> compte_resultat.resultat
