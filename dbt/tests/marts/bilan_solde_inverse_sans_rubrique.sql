-- H8 : aucun compte de bilan au solde inversé (au niveau de l'IMF, en fin de mois) sans
-- rubrique_solde_inverse ; sinon le bilan compenserait une dette avec un actif, ou l'inverse.
with soldes as (
    select
        b.date_fin_mois,
        b.code_compte,
        sum(b.solde_cloture_debit - b.solde_cloture_credit) as solde
    from {{ ref('mart_balance') }} as b
    group by b.date_fin_mois, b.code_compte
)

select s.date_fin_mois, s.code_compte, c.sens_normal, s.solde
from soldes as s
inner join {{ ref('dim_compte_comptable') }} as c on c.code_compte = s.code_compte
where c.etat = 'BILAN'
    and c.rubrique_solde_inverse is null
    and ((c.sens_normal = 'D' and s.solde < 0) or (c.sens_normal = 'C' and s.solde > 0))
