-- D19 : la banque (TRESO_BANQUE) est ≥ 0 au niveau de l'IMF à chaque fin de mois.
select date_fin_mois, sum(solde_cloture_debit - solde_cloture_credit) as solde_banque
from {{ ref('mart_balance') }}
where code_compte = 'TRESO_BANQUE'
group by date_fin_mois
having sum(solde_cloture_debit - solde_cloture_credit) < 0
