-- Catalogue (2) : aucune ligne écartée hors catalogue (garde-fou contre les faux positifs).
select e.table_source, e.id_ligne, e.motif_ecart
from {{ ref('slv_lignes_ecartees') }} as e
left join {{ ref('stg_catalogue_anomalies') }} as c
    on c.table_source = e.table_source
    and c.id_ligne = e.id_ligne
    and c.nature = e.motif_ecart
    and c.traitement_attendu = e.traitement
where c.id_ligne is null
