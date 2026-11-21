-- Agences, siège compris (type_agence = SIEGE).
select
    id_agence,
    nom,
    ville,
    region,
    type_agence,
    cast(type_agence = 'SIEGE' as boolean) as est_siege
from {{ ref('slv_agences') }}
