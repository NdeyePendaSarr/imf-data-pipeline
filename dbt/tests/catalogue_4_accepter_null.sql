-- Catalogue (4) : chaque ligne ACCEPTER_NULL est présente dans slv_clients, avec son NULL.
select c.id_ligne
from {{ ref('stg_catalogue_anomalies') }} as c
left join {{ ref('slv_clients') }} as s on s.id_client = c.id_ligne
where c.table_source = 'clients'
    and c.traitement_attendu = 'ACCEPTER_NULL'
    and c.date_ligne <= {{ date_arrete() }}
    and (s.id_client is null or (s.secteur_activite is not null and s.date_naissance is not null))
