-- Crédits : conditions d'octroi. statut_au_31_12 garde son nom : il reflète l'état au 31/12
-- dès le décaissement (I10) et ne doit jamais servir à une analyse à date.
select
    c.id_credit,
    id_client,
    id_compte_epargne,
    code_produit,
    date_decaissement,
    montant_accorde,
    frais_dossier,
    duree_mois,
    taux_annuel,
    statut_au_31_12,
    -- Statut à la date d'arrêté, déduit des remboursements de capital jusqu'à l'arrêté, avec la
    -- même règle que fct_portefeuille_quotidien (encours > 0 → EN_COURS). Au 31/12 il est égal
    -- à statut_au_31_12 (test dim_credit_statut_a_l_arrete).
    cast(case
        when coalesce(r.capital_rembourse, 0) >= c.montant_accorde then 'SOLDE'
        else 'EN_COURS'
    end as text) as statut_a_l_arrete
from {{ ref('slv_credits') }} as c
left join (
    select id_credit, sum(part_capital) as capital_rembourse
    from {{ ref('slv_remboursements') }}
    where date_remboursement <= {{ date_arrete() }}
    group by id_credit
) as r on r.id_credit = c.id_credit
-- Seuls les crédits décaissés à l'arrêté existent à cette date.
where c.date_decaissement <= {{ date_arrete() }}
