-- Mouvements des comptes clients (S10) : une ligne par mouvement, une seule source par mouvement.
-- montant_signe > 0 augmente le solde du compte, < 0 le diminue.
with operations as (
    -- Dépôts (+), retraits (−) et frais de tenue (−) enregistrés par les agences.
    select
        id_compte,
        date_operation as date,
        type_operation as type_mouvement,
        case when type_operation = 'DEPOT' then montant else -montant end as montant_signe,
        'slv_operations' as source_table,
        id_operation as source_id
    from {{ ref('slv_operations') }}
),

decaissements as (
    -- Le crédit est versé sur le compte d'épargne du client.
    select
        id_compte_epargne as id_compte,
        date_decaissement as date,
        'DECAISSEMENT' as type_mouvement,
        montant_accorde as montant_signe,
        'slv_credits' as source_table,
        id_credit as source_id
    from {{ ref('slv_credits') }}
),

frais_dossier as (
    -- Les frais de dossier sont prélevés sur ce même compte, le jour du décaissement.
    select
        id_compte_epargne as id_compte,
        date_decaissement as date,
        'FRAIS_DOSSIER' as type_mouvement,
        -frais_dossier as montant_signe,
        'slv_credits' as source_table,
        id_credit as source_id
    from {{ ref('slv_credits') }}
    where frais_dossier > 0
),

prelevements as (
    -- Remboursement par prélèvement : débit du compte d'épargne du crédit.
    select
        c.id_compte_epargne as id_compte,
        r.date_remboursement as date,
        'PRELEVEMENT' as type_mouvement,
        -r.montant_paye as montant_signe,
        'slv_remboursements' as source_table,
        r.id_remboursement as source_id
    from {{ ref('slv_remboursements') }} as r
    inner join {{ ref('slv_credits') }} as c on c.id_credit = r.id_credit
    where r.canal = 'PRELEVEMENT'
),

mouvements as (
    select * from operations
    union all
    select * from decaissements
    union all
    select * from frais_dossier
    union all
    select * from prelevements
)

select
    -- Identifiant déterministe et lisible : type du mouvement + identifiant de la ligne source.
    cast(type_mouvement || ':' || source_id as {{ dbt.type_string() }}) as id_mouvement,
    cast(id_compte as {{ dbt.type_string() }}) as id_compte,
    cast(date as date) as date,
    cast(type_mouvement as {{ dbt.type_string() }}) as type_mouvement,
    cast(montant_signe as bigint) as montant_signe,
    cast(source_table as {{ dbt.type_string() }}) as source_table,
    cast(source_id as {{ dbt.type_string() }}) as source_id
from mouvements
