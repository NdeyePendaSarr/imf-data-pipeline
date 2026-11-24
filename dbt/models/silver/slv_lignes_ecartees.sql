-- Toutes les lignes écartées du silver, avec leur motif et leur traçabilité bronze (S3).
-- Rien n'est filtré en silence : chaque ligne absente d'un slv_* est ici.
{#- Échéancier : num_echeance est un entier ; || le convertit seul en PostgreSQL, pas en
    BigQuery, d'où le cast explicite. #}
{%- set sources = [
    ('agences', 'stg_agences', 'id_agence'),
    ('ouverture', 'stg_ouverture', 'id_ligne'),
    ('operations', 'stg_operations', 'id_operation'),
    ('charges', 'stg_charges', 'id_charge'),
    ('appro_caisse', 'stg_appro_caisse', 'id_appro'),
    ('produits_credit', 'stg_produits_credit', 'code_produit'),
    ('clients', 'stg_clients', 'id_client'),
    ('comptes', 'stg_comptes', 'id_compte'),
    ('credits', 'stg_credits', 'id_credit'),
    ('echeancier', 'stg_echeancier', "id_credit || '|' || cast(num_echeance as " ~ dbt.type_string() ~ ")"),
    ('remboursements', 'stg_remboursements', 'id_remboursement'),
] %}

{% for table_source, modele, identifiant in sources %}
select
    cast('{{ table_source }}' as {{ dbt.type_string() }}) as table_source,
    cast({{ identifiant }} as {{ dbt.type_string() }}) as id_ligne,
    cast(motif_ecart as {{ dbt.type_string() }}) as motif_ecart,
    -- Une copie de doublon exact se dédoublonne ; tout autre motif se rejette.
    cast(case when motif_ecart = 'DOUBLON_EXACT' then 'DEDOUBLONNER' else 'REJETER' end as {{ dbt.type_string() }})
        as traitement,
    cast(_id_run as {{ dbt.type_string() }}) as _id_run,
    cast(_source as {{ dbt.type_string() }}) as _source,
    cast(_num_ligne as integer) as _num_ligne
from {{ ref(modele) }}
where motif_ecart is not null
{% if not loop.last %}union all{% endif %}
{% endfor %}
