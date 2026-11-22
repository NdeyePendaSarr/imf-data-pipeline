-- Opérations des comptes clients, une ligne par opération (silver dédoublonné et valide).
-- est_activite_client = false pour FRAIS_TENUE (G12) : prélevés par l'IMF, ils ne mesurent pas
-- l'activité du client et sont exclus des KPI d'activité (mais restent de vraies écritures, S15).
select
    o.id_operation,
    o.date_operation,
    o.id_compte,
    c.id_client,
    o.id_agence,
    o.type_operation,
    o.canal,
    o.montant,
    cast(o.type_operation <> 'FRAIS_TENUE' as boolean) as est_activite_client
from {{ ref('slv_operations') }} as o
inner join {{ ref('slv_comptes') }} as c on c.id_compte = o.id_compte
where o.date_operation <= {{ date_arrete() }}
