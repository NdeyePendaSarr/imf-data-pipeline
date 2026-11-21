-- Crédits : conditions d'octroi. statut_au_31_12 garde son nom : il reflète l'état au 31/12
-- dès le décaissement (I10) et ne doit jamais servir à une analyse à date.
select
    id_credit,
    id_client,
    id_compte_epargne,
    code_produit,
    date_decaissement,
    montant_accorde,
    frais_dossier,
    duree_mois,
    taux_annuel,
    statut_au_31_12
from {{ ref('slv_credits') }}
