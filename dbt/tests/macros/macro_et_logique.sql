-- et_logique : vrai seulement si l'expression est vraie sur toutes les lignes du groupe.
with valeurs as (
    select 'A' as groupe, 'PRODUIT' as nature
    union all select 'A', 'PRODUIT'
    union all select 'B', 'PRODUIT'
    union all select 'B', 'CHARGE'
),
obtenu as (
    select groupe, {{ et_logique("nature = 'PRODUIT'") }} as tous_produits
    from valeurs
    group by groupe
)
select *
from obtenu
where (groupe = 'A' and tous_produits is distinct from true)
    or (groupe = 'B' and tous_produits is distinct from false)
