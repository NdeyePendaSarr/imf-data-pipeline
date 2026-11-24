-- Clients (imf_ops) : dernière version par client (S8). Les NULL de date_naissance et
-- secteur_activite sont acceptés (ACCEPTER_NULL) : ils ne sont pas un motif d'écart.
with versions as (
    select
        *,
        row_number() over (partition by id_client order by date_maj desc, _charge_le desc) as rang_version
    from {{ source('bronze', 'ops_clients') }}
)

select
    id_client,
    id_agence,
    prenom,
    nom,
    {{ standardiser('sexe') }} as sexe,
    date_naissance,
    {{ standardiser('secteur_activite') }} as secteur_activite,
    date_adhesion,
    date_maj,
    _id_run,
    _source,
    _num_ligne,
    cast(null as {{ dbt.type_string() }}) as motif_ecart
from versions
where rang_version = 1
