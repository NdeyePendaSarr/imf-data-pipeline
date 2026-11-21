-- L'imputation FIFO reste entre 0 et le montant dû ; une échéance couverte l'est en entier.
select id_credit, num_echeance, montant_du, montant_impute_au_31_12, date_couverture
from {{ ref('fct_echeances') }}
where montant_impute_au_31_12 > montant_du
    or (date_couverture is not null and montant_impute_au_31_12 <> montant_du)
