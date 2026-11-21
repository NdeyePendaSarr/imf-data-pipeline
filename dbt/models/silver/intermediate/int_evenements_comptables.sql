-- Événements comptables de l'exercice (G1, G2, G6, G7), construits depuis les slv_* (jamais
-- depuis int_mouvements_compte). Format long : une ligne par événement et par champ montant,
-- pour la jointure avec mapping_comptable (type_evenement, source, champ_montant).
--   source_table = colonne « source » de mapping_comptable ; source_id = identifiant de la ligne ;
--   id_agence = agence du client pour operations, credits, remboursements, de la source sinon ;
--   canal = canal de la source (NULL pour appro_caisse et credits, sans ligne @TRESORERIE).

with agence_compte as (
    -- Agence de chaque compte client, via son titulaire.
    select comptes.id_compte, clients.id_agence
    from {{ ref('slv_comptes') }} as comptes
    inner join {{ ref('slv_clients') }} as clients on clients.id_client = comptes.id_client
),

agence_credit as (
    select credits.id_credit, clients.id_agence
    from {{ ref('slv_credits') }} as credits
    inner join {{ ref('slv_clients') }} as clients on clients.id_client = credits.id_client
),

evenements as (
    -- Ouverture du 01/01 : capital en banque (VIREMENT) et fonds de caisse (GUICHET).
    select
        'OUVERTURE' as type_evenement,
        'ouverture' as source_table,
        id_agence || '|' || canal as source_id,
        cast('{{ var("exercice") }}-01-01' as date) as date_evenement,
        id_agence,
        canal,
        'montant' as champ_montant,
        montant
    from {{ ref('slv_ouverture') }}

    union all

    -- Approvisionnement de caisse (D18) : deux comptes fixes, pas de canal.
    select
        'APPRO_CAISSE', 'appro_caisse', id_appro, date_appro, id_agence,
        cast(null as text), 'montant', montant
    from {{ ref('slv_appro_caisse') }}

    union all

    -- Opérations des comptes : le type d'événement est le type d'opération.
    select
        o.type_operation, 'operations', o.id_operation, o.date_operation, a.id_agence,
        o.canal, 'montant', o.montant
    from {{ ref('slv_operations') }} as o
    inner join agence_compte as a on a.id_compte = o.id_compte

    union all

    -- Crédit : deux événements, le décaissement et les frais de dossier.
    select
        'DECAISSEMENT', 'credits', c.id_credit, c.date_decaissement, a.id_agence,
        cast(null as text), 'montant_accorde', c.montant_accorde
    from {{ ref('slv_credits') }} as c
    inner join agence_credit as a on a.id_credit = c.id_credit

    union all

    select
        'FRAIS_DOSSIER', 'credits', c.id_credit, c.date_decaissement, a.id_agence,
        cast(null as text), 'frais_dossier', c.frais_dossier
    from {{ ref('slv_credits') }} as c
    inner join agence_credit as a on a.id_credit = c.id_credit

    union all

    -- Remboursement : un événement, quatre champs montant (payé, capital, intérêts, pénalités).
    select
        'REMBOURSEMENT', 'remboursements', r.id_remboursement, r.date_remboursement, a.id_agence,
        r.canal, champs.champ_montant, champs.montant
    from {{ ref('slv_remboursements') }} as r
    inner join agence_credit as a on a.id_credit = r.id_credit
    cross join lateral (
        values
            ('montant_paye', r.montant_paye),
            ('part_capital', r.part_capital),
            ('part_interets', r.part_interets),
            ('penalites', r.penalites)
    ) as champs (champ_montant, montant)

    union all

    -- Charges : le type d'événement est CHARGE_ suivi de la catégorie.
    select
        'CHARGE_' || categorie, 'charges', id_charge, date_charge, id_agence,
        canal, 'montant', montant
    from {{ ref('slv_charges') }}
)

select
    cast(type_evenement as text) as type_evenement,
    cast(source_table as text) as source_table,
    cast(source_id as text) as source_id,
    cast(date_evenement as date) as date_evenement,
    cast(id_agence as text) as id_agence,
    cast(canal as text) as canal,
    cast(champ_montant as text) as champ_montant,
    cast(montant as bigint) as montant
from evenements
