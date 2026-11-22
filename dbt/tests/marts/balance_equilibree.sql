-- Partie double dans la balance : par agence × mois, Σ mouvements D = Σ mouvements C et
-- Σ soldes de clôture D = Σ soldes de clôture C (chaque pièce porte une seule agence).
select
    id_agence,
    date_fin_mois,
    sum(mouvement_debit) as mvt_d,
    sum(mouvement_credit) as mvt_c,
    sum(solde_cloture_debit) as clot_d,
    sum(solde_cloture_credit) as clot_c
from {{ ref('mart_balance') }}
group by id_agence, date_fin_mois
having sum(mouvement_debit) <> sum(mouvement_credit)
    or sum(solde_cloture_debit) <> sum(solde_cloture_credit)
