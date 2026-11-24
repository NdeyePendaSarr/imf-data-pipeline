-- D17 : la rubrique d'un compte est cohérente avec sa nature. Un compte CHARGE est rangé dans
-- une rubrique de charges, un compte PRODUIT dans une rubrique de produits (une charge dans une
-- rubrique de produits fausserait le compte de résultat), et un compte de bilan à l'actif (A…)
-- ou au passif (P…) selon sa nature.
with classement as (
    -- Sens de chaque rubrique du compte de résultat. R5_COUT_DU_RISQUE est volontairement mixte :
    -- dotations (charge) et reprises (produit) s'y compensent pour donner le coût du risque net.
    -- union all de select : SQL standard ((values …) as c (…) n'existe pas en BigQuery).
    select 'R1_PRODUITS_FINANCIERS' as rubrique, 'PRODUIT' as sens_rubrique
    union all select 'R2_COMMISSIONS', 'PRODUIT'
    union all select 'R3_CHARGES_PERSONNEL', 'CHARGE'
    union all select 'R4_CHARGES_GENERALES', 'CHARGE'
    union all select 'R5_COUT_DU_RISQUE', 'MIXTE'
    union all select 'R6_CHARGES_FINANCIERES', 'CHARGE'
)

select comptes.code_compte, comptes.nature, comptes.etat, comptes.rubrique, classement.sens_rubrique
from {{ ref('dim_compte_comptable') }} as comptes
left join classement on classement.rubrique = comptes.rubrique
where
    -- Compte de résultat : rubrique classée, de même sens que la nature (ou mixte).
    (comptes.nature in ('CHARGE', 'PRODUIT') and (
        comptes.etat <> 'CR'
        or classement.sens_rubrique is null
        or classement.sens_rubrique not in (comptes.nature, 'MIXTE')
    ))
    -- Bilan : actif en A…, passif en P….
    or (comptes.nature = 'ACTIF' and (comptes.etat <> 'BILAN' or comptes.rubrique not like 'A%'))
    or (comptes.nature = 'PASSIF' and (comptes.etat <> 'BILAN' or comptes.rubrique not like 'P%'))
    -- Une rubrique en R… n'accueille que des comptes de résultat.
    or (comptes.rubrique like 'R%' and comptes.nature not in ('CHARGE', 'PRODUIT'))
