-- Comptes (imf_ops) : dernière version par compte (S8).
with versions as (
    select
        *,
        row_number() over (partition by id_compte order by date_maj desc, _charge_le desc) as rang_version
    from {{ source('bronze', 'ops_comptes') }}
)

select
    id_compte,
    id_client,
    {{ standardiser('type_compte') }} as type_compte,
    date_ouverture,
    {{ standardiser('statut') }} as statut,
    date_maj,
    _id_run,
    _source,
    _num_ligne,
    cast(null as {{ dbt.type_string() }}) as motif_ecart
from versions
where rang_version = 1
