{#
  Typage sûr des colonnes TEXT du bronze (décision S4) : une valeur non convertible donne NULL
  au lieu de faire échouer le build ; la ligne est alors écartée avec le motif TYPE_INVALIDE.
#}

{# Entier signé (montants XOF) : au plus 18 chiffres pour rester dans un BIGINT. #}
{% macro vers_bigint(colonne) -%}
    case when trim({{ colonne }}) ~ '^[-+]?[0-9]{1,18}$' then trim({{ colonne }})::bigint end
{%- endmacro %}

{#
  Date ISO AAAA-MM-JJ réellement existante (pas de 30/02). Les CASE imbriqués garantissent
  l'ordre d'évaluation : make_date n'est appelé que sur un mois valide.
#}
{% macro vers_date(colonne) -%}
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

{# Standardisation des codes (canal, type, catégorie) : « guichet », « Mobile » → GUICHET, MOBILE (S5). #}
{% macro standardiser(colonne) -%}
    upper(trim({{ colonne }}))
{%- endmacro %}
