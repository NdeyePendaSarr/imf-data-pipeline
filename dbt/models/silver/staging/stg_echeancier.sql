-- Échéancier théorique (imf_ops) : dernière version par (crédit, numéro d'échéance) (S8).
with versions as (
    select
        *,
        row_number() over (
            partition by id_credit, num_echeance order by date_maj desc, _charge_le desc
        ) as rang_version
    from {{ source('bronze', 'ops_echeancier') }}
)

select
    id_credit,
    num_echeance,
    date_echeance,
    capital,
    interets,
    montant,
    date_maj,
    _id_run,
    _source,
    _num_ligne,
    case when capital < 0 or interets < 0 or montant < 0 then 'MONTANT_NEGATIF' end as motif_ecart
from versions
where rang_version = 1
