-- Catalogue (3) : chaque ligne STANDARDISER est présente dans silver avec un canal autorisé.
select c.id_ligne, o.canal
from {{ ref('stg_catalogue_anomalies') }} as c
left join {{ ref('slv_operations') }} as o on o.id_operation = c.id_ligne
where c.table_source = 'operations'
    and c.traitement_attendu = 'STANDARDISER'
    and (
        o.id_operation is null
        or not exists (
            select 1 from {{ ref('canaux_autorises') }} as a
            where a.source = 'operations' and a.canal = o.canal
        )
    )
