-- Crédits (imf_ops) : dernière version par crédit (S8). Le statut est celui du 31/12 (I10).
with versions as (
    select
        *,
        row_number() over (partition by id_credit order by date_maj desc, _charge_le desc) as rang_version
    from {{ source('bronze', 'ops_credits') }}
)

select
    id_credit,
    id_client,
    id_compte_epargne,
    {{ standardiser('code_produit') }} as code_produit,
    date_decaissement,
    montant_accorde,
    frais_dossier,
    duree_mois,
    taux_annuel,
    {{ standardiser('statut') }} as statut,
    date_maj,
    _id_run,
    _source,
    _num_ligne,
    case when montant_accorde < 0 or frais_dossier < 0 then 'MONTANT_NEGATIF' end as motif_ecart
from versions
where rang_version = 1
