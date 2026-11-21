{#
  Schéma exact (silver, gold) sans préfixe de cible : dbt produirait sinon « silver_silver »
  ou « dev_silver » (décision S2). Sans schéma personnalisé, on garde celui du profil.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
