-- Cumul de décembre du compte de résultat = Σ produits − Σ charges de fct_ecritures
-- (produits : crédit − débit ; charges : débit − crédit).
with ecritures as (
    select
        sum(case when c.nature = 'PRODUIT' then e.credit - e.debit else 0 end)
            - sum(case when c.nature = 'CHARGE' then e.debit - e.credit else 0 end) as resultat
    from {{ ref('fct_ecritures') }} as e
    inner join {{ ref('dim_compte_comptable') }} as c on c.code_compte = e.code_compte
),

compte_resultat as (
    select sum(resultat_cumul) as resultat
    from {{ ref('mart_compte_resultat') }}
    where date_fin_mois = cast('{{ var("exercice") }}-12-31' as date)
)

select ecritures.resultat as ecritures, compte_resultat.resultat as compte_resultat
from ecritures cross join compte_resultat
where ecritures.resultat is distinct from compte_resultat.resultat
