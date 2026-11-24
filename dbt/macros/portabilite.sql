{#
  Portabilité PostgreSQL / BigQuery du gold (phase 9, L6) : fonctions sans équivalent dans les
  macros dbt. Une implémentation par moteur (adapter.dispatch) ; default__ échoue.
  Testées sur des valeurs littérales par dbt/tests/macros/, sur les deux cibles.
#}

{# ET logique d'agrégat : vrai si l'expression est vraie sur toutes les lignes du groupe. #}
{% macro et_logique(expression) -%}
    {{ return(adapter.dispatch('et_logique')(expression)) }}
{%- endmacro %}

{% macro postgres__et_logique(expression) -%}bool_and({{ expression }}){%- endmacro %}

{% macro bigquery__et_logique(expression) -%}logical_and({{ expression }}){%- endmacro %}

{% macro default__et_logique(expression) -%}
    {{ exceptions.raise_compiler_error("et_logique : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}

{# Mois d'une date au format texte AAAA-MM. #}
{% macro annee_mois(date) -%}
    {{ return(adapter.dispatch('annee_mois')(date)) }}
{%- endmacro %}

{% macro postgres__annee_mois(date) -%}to_char({{ date }}, 'YYYY-MM'){%- endmacro %}

{% macro bigquery__annee_mois(date) -%}format_date('%Y-%m', {{ date }}){%- endmacro %}

{% macro default__annee_mois(date) -%}
    {{ exceptions.raise_compiler_error("annee_mois : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}

{#
  Jour de la semaine ISO : 1 = lundi … 7 = dimanche. BigQuery : FORMAT_DATE('%u') (jour ISO), et
  surtout pas EXTRACT(DAYOFWEEK), qui renvoie 1 = dimanche … 7 = samedi.
#}
{% macro jour_iso(date) -%}
    {{ return(adapter.dispatch('jour_iso')(date)) }}
{%- endmacro %}

{% macro postgres__jour_iso(date) -%}extract(isodow from {{ date }}){%- endmacro %}

{% macro bigquery__jour_iso(date) -%}cast(format_date('%u', {{ date }}) as int64){%- endmacro %}

{% macro default__jour_iso(date) -%}
    {{ exceptions.raise_compiler_error("jour_iso : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}

{#
  Âge en années révolues à la date `arrete` pour une naissance `naissance`.
  PostgreSQL : extract(year from age(arrete, naissance)).
  BigQuery : DATE_DIFF(…, YEAR) compte les changements d'année civile ; on retire 1 si
  l'anniversaire (mois-jour) n'est pas encore atteint. Aligné sur PostgreSQL pour un né le 29/02,
  une année non bissextile : 28/02 → anniversaire pas atteint (année − 1), 01/03 → atteint
  (vérifié par dbt/tests/macros/macro_age_revolu.sql).
#}
{% macro age_revolu(arrete, naissance) -%}
    {{ return(adapter.dispatch('age_revolu')(arrete, naissance)) }}
{%- endmacro %}

{% macro postgres__age_revolu(arrete, naissance) -%}
    extract(year from age({{ arrete }}, {{ naissance }}))
{%- endmacro %}

{% macro bigquery__age_revolu(arrete, naissance) -%}
    (date_diff({{ arrete }}, {{ naissance }}, year)
        - case when format_date('%m%d', {{ arrete }}) < format_date('%m%d', {{ naissance }})
            then 1 else 0 end)
{%- endmacro %}

{% macro default__age_revolu(arrete, naissance) -%}
    {{ exceptions.raise_compiler_error("age_revolu : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}
