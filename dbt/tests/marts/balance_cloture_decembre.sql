-- Clôture de décembre = Σ (débit − crédit) de fct_ecritures sur l'exercice, par compte × agence.
with ecritures as (
    select code_compte, id_agence, sum(debit - credit) as solde
    from {{ ref('fct_ecritures') }}
    group by code_compte, id_agence
),

decembre as (
    select code_compte, id_agence, solde_cloture_debit - solde_cloture_credit as solde
    from {{ ref('mart_balance') }}
    where date_fin_mois = cast('{{ var("exercice") }}-12-31' as date)
)

select coalesce(e.code_compte, d.code_compte) as code_compte,
    coalesce(e.id_agence, d.id_agence) as id_agence, e.solde as ecritures, d.solde as balance
from ecritures as e
full outer join decembre as d on d.code_compte = e.code_compte and d.id_agence = e.id_agence
where e.solde is distinct from d.solde
