-- Continuité : la clôture du mois m est l'ouverture du mois m + 1 (débit et crédit).
with suite as (
    select
        *,
        lead(solde_ouverture_debit) over w as ouverture_debit_suivante,
        lead(solde_ouverture_credit) over w as ouverture_credit_suivante
    from {{ ref('mart_balance') }}
    window w as (partition by code_compte, id_agence order by date_fin_mois)
)

select code_compte, id_agence, date_fin_mois
from suite
where ouverture_debit_suivante is not null
    and (solde_cloture_debit <> ouverture_debit_suivante
        or solde_cloture_credit <> ouverture_credit_suivante)
