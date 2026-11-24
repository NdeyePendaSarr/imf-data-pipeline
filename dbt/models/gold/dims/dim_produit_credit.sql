-- Produits de crédit : taux, frais de dossier, durées ; échéances toujours mensuelles.
select
    code_produit,
    libelle,
    taux_annuel,
    taux_frais_dossier,
    duree_min_mois,
    duree_max_mois,
    cast('MENSUELLE' as {{ dbt.type_string() }}) as periodicite
from {{ ref('slv_produits_credit') }}
