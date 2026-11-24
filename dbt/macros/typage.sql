{#
  Typage sûr des colonnes TEXT du bronze (décision S4) : une valeur non convertible donne NULL
  au lieu de faire échouer le build ; la ligne est alors écartée avec le motif TYPE_INVALIDE.
#}

{#
  Portabilité PostgreSQL / BigQuery (phase 9, L6) : expressions régulières et casts n'ont pas la
  même syntaxe ; chaque macro choisit son implémentation par adapter.dispatch selon le moteur.
  Même contrat des deux côtés : texte invalide → NULL, jamais d'erreur.
#}

{# Entier signé (montants XOF) : au plus 18 chiffres pour rester dans un BIGINT / INT64. #}
{% macro vers_bigint(colonne) -%}
    {{ return(adapter.dispatch('vers_bigint')(colonne)) }}
{%- endmacro %}

{% macro postgres__vers_bigint(colonne) -%}
    case when trim({{ colonne }}) ~ '^[-+]?[0-9]{1,18}$' then trim({{ colonne }})::bigint end
{%- endmacro %}

{% macro bigquery__vers_bigint(colonne) -%}
    case
        when regexp_contains(trim({{ colonne }}), r'^[-+]?[0-9]{1,18}$')
            then cast(trim({{ colonne }}) as int64)
    end
{%- endmacro %}

{% macro default__vers_bigint(colonne) -%}
    {{ exceptions.raise_compiler_error("vers_bigint : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}

{#
  Date ISO AAAA-MM-JJ réellement existante (pas de 30/02).
  PostgreSQL : les CASE imbriqués garantissent l'ordre d'évaluation ; make_date n'est appelé que
  sur un mois valide. BigQuery : SAFE.PARSE_DATE renvoie NULL pour une date qui n'existe pas.
#}
{% macro vers_date(colonne) -%}
    {{ return(adapter.dispatch('vers_date')(colonne)) }}
{%- endmacro %}

{% macro postgres__vers_date(colonne) -%}
    case
        when trim({{ colonne }}) ~ '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$' then
            case
                when substr(trim({{ colonne }}), 9, 2)::int <= extract(day from (
                    make_date(substr(trim({{ colonne }}), 1, 4)::int, substr(trim({{ colonne }}), 6, 2)::int, 1)
                    + interval '1 month' - interval '1 day'))
                then trim({{ colonne }})::date
            end
    end
{%- endmacro %}

{% macro bigquery__vers_date(colonne) -%}
    case
        when regexp_contains(trim({{ colonne }}), r'^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$')
            then safe.parse_date('%Y-%m-%d', trim({{ colonne }}))
    end
{%- endmacro %}

{% macro default__vers_date(colonne) -%}
    {{ exceptions.raise_compiler_error("vers_date : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}

{#
  Horodatage local sans fuseau (date_maj : date de l'événement à 20:00). PostgreSQL : timestamp
  (sans fuseau) ; BigQuery : DATETIME. Un TIMESTAMP BigQuery est un instant UTC : y caster
  date_maj changerait son sens. Aucune macro dbt ne couvre ce type (dbt.type_timestamp() donne
  TIMESTAMP en BigQuery).
#}
{% macro type_datetime() -%}
    {{ return(adapter.dispatch('type_datetime')()) }}
{%- endmacro %}

{% macro postgres__type_datetime() -%}timestamp{%- endmacro %}

{% macro bigquery__type_datetime() -%}datetime{%- endmacro %}

{#
  Taux (taux annuel, frais de dossier : 4 décimales). PostgreSQL : numeric(6,4). BigQuery refuse
  les types paramétrés dans un CAST (« Parameterized types are not allowed in CAST
  expressions ») : NUMERIC (38 chiffres, 9 décimales), qui contient les mêmes valeurs.
#}
{% macro type_taux() -%}
    {{ return(adapter.dispatch('type_taux')()) }}
{%- endmacro %}

{% macro postgres__type_taux() -%}numeric(6,4){%- endmacro %}

{% macro bigquery__type_taux() -%}numeric{%- endmacro %}

{% macro default__type_taux() -%}
    {{ exceptions.raise_compiler_error("type_taux : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}

{% macro default__type_datetime() -%}
    {{ exceptions.raise_compiler_error("type_datetime : moteur non pris en charge " ~ target.type) }}
{%- endmacro %}

{# Standardisation des codes (canal, type, catégorie) : « guichet », « Mobile » → GUICHET, MOBILE (S5). #}
{% macro standardiser(colonne) -%}
    upper(trim({{ colonne }}))
{%- endmacro %}
