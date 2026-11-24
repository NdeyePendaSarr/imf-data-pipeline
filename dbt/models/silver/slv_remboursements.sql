-- Remboursements valides, dernière version.
-- Lignes de stg_remboursements sans motif d'écart ; noms de colonnes de la source (S13).
select
    cast(id_remboursement as {{ dbt.type_string() }}) as id_remboursement,
    cast(id_credit as {{ dbt.type_string() }}) as id_credit,
    cast(date_remboursement as date) as date_remboursement,
    cast(montant_paye as bigint) as montant_paye,
    cast(part_capital as bigint) as part_capital,
    cast(part_interets as bigint) as part_interets,
    cast(penalites as bigint) as penalites,
    cast(canal as {{ dbt.type_string() }}) as canal,
    cast(date_maj as {{ type_datetime() }}) as date_maj,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source
from {{ ref('stg_remboursements') }}
where motif_ecart is null
