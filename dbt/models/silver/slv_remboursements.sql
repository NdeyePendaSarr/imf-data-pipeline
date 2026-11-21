-- Remboursements valides, dernière version.
-- Lignes de stg_remboursements sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_remboursement as text) as id_remboursement,
    cast(id_credit as text) as id_credit,
    cast(date_remboursement as date) as date_remboursement,
    cast(montant_paye as bigint) as montant_paye,
    cast(part_capital as bigint) as part_capital,
    cast(part_interets as bigint) as part_interets,
    cast(penalites as bigint) as penalites,
    cast(canal as text) as canal,
    cast(date_maj as timestamp) as date_maj,
    cast(_id_run as text) as _id_run,
    cast(_source as text) as _source
from {{ ref('stg_remboursements') }}
where motif_ecart is null
