-- Produits de crédit (imf_ops) : dernière version par code (S8).
with versions as (
    select
        *,
        row_number() over (
            partition by code_produit order by date_maj desc, _charge_le desc
        ) as rang_version
    from {{ source('bronze', 'ops_produits_credit') }}
)

select
    {{ standardiser('code_produit') }} as code_produit,
    libelle,
    taux_annuel,
    taux_frais_dossier,
    duree_min_mois,
    duree_max_mois,
    date_maj,
    _id_run,
    _source,
    _num_ligne,
    case when taux_annuel < 0 or taux_frais_dossier < 0 then 'MONTANT_NEGATIF' end as motif_ecart
from versions
where rang_version = 1
