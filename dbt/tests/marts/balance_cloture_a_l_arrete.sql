-- Clôture du dernier mois présent dans la balance (mois de l'arrêté, éventuellement partiel)
-- = Σ (débit − crédit) de fct_ecritures jusqu'à la date d'arrêté, par compte × agence.
with ecritures as (
    select code_compte, id_agence, sum(debit - credit) as solde
    from {{ ref('fct_ecritures') }}
    where date_ecriture <= {{ date_arrete() }}
    group by code_compte, id_agence
),

dernier_mois as (
    select code_compte, id_agence, solde_cloture_debit - solde_cloture_credit as solde
    from {{ ref('mart_balance') }}
    where date_fin_mois = (select max(date_fin_mois) from {{ ref('mart_balance') }})
)

select coalesce(e.code_compte, d.code_compte) as code_compte,
    coalesce(e.id_agence, d.id_agence) as id_agence, e.solde as ecritures, d.solde as balance
from ecritures as e
full outer join dernier_mois as d on d.code_compte = e.code_compte and d.id_agence = e.id_agence
where e.solde is distinct from d.solde
