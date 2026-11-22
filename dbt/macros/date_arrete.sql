{#
  Date d'arrêté des comptes et des indicateurs (phase 7, lot A). Défaut : dernier jour de
  l'exercice (var exercice). Surcharge : dbt build --vars '{date_arrete: "2025-03-31"}'.
  Le gold ne porte aucun événement daté après cette date ; seuls dim_date (calendrier) et les
  dates prévues des échéances futures (fct_echeances.date_prevue) la dépassent, par nature.
#}
{% macro date_arrete() -%}
    {%- set valeur = var('date_arrete', none) -%}
    {%- if valeur is none or valeur == '' -%}
        {%- set valeur = var('exercice') ~ '-12-31' -%}
    {%- endif -%}
    cast('{{ valeur }}' as date)
{%- endmacro %}
