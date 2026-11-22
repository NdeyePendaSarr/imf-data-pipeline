-- Jusqu'à la date d'arrêté (l'ouverture est au 01/01). Par type d'événement, Σ des montants de la source (lus directement dans silver, sans passer
-- par les événements ni par le mapping) = Σ des débits des pièces de ce type.
with source as (
    select type_operation as type_evenement, sum(montant) as montant
    from {{ ref('slv_operations') }} where date_operation <= {{ date_arrete() }} group by type_operation
    union all
    select 'DECAISSEMENT', sum(montant_accorde) from {{ ref('slv_credits') }} where date_decaissement <= {{ date_arrete() }}
    union all
    select 'FRAIS_DOSSIER', sum(frais_dossier) from {{ ref('slv_credits') }} where date_decaissement <= {{ date_arrete() }}
    union all
    select 'REMBOURSEMENT', sum(montant_paye) from {{ ref('slv_remboursements') }} where date_remboursement <= {{ date_arrete() }}
    union all
    select 'CHARGE_' || categorie, sum(montant) from {{ ref('slv_charges') }} where date_charge <= {{ date_arrete() }} group by categorie
    union all
    select 'OUVERTURE', sum(montant) from {{ ref('slv_ouverture') }}
    union all
    select 'APPRO_CAISSE', sum(montant) from {{ ref('slv_appro_caisse') }} where date_appro <= {{ date_arrete() }}
),

ecritures as (
    select type_evenement, sum(debit) as debit
    from {{ ref('fct_ecritures') }}
    group by type_evenement
)

select source.type_evenement, source.montant, ecritures.debit
from source
full outer join ecritures using (type_evenement)
where source.montant is distinct from ecritures.debit
