-- Calendrier : un jour par ligne, de l'ouverture de l'exercice au 31/12 de la dernière année
-- d'échéances (var exercice + annees_apres_exercice). Jouée en plusieurs rôles dans les faits.
{%- set debut = var('exercice') ~ '-01-01' %}
{%- set fin = (var('exercice') + var('annees_apres_exercice') + 1) ~ '-01-01' %}

with jours as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ debut ~ "' as date)",
        end_date="cast('" ~ fin ~ "' as date)"
    ) }}
)

select
    cast(date_day as date) as date,
    cast(extract(year from date_day) as integer) as annee,
    cast(extract(month from date_day) as integer) as mois,
    cast(to_char(date_day, 'YYYY-MM') as text) as annee_mois,
    cast(extract(quarter from date_day) as integer) as trimestre,
    cast(extract(isodow from date_day) as integer) as jour_semaine,
    -- Exercice comptable de la date (année civile) et appartenance à l'exercice analysé.
    cast(extract(year from date_day) as integer) as exercice,
    cast(extract(year from date_day) = {{ var('exercice') }} as boolean) as dans_exercice,
    cast(date_day = (date_trunc('month', date_day) + interval '1 month - 1 day')::date as boolean)
        as est_fin_de_mois,
    -- Guichet et agents : lundi à samedi, sans jours fériés (Limites).
    cast(extract(isodow from date_day) <= 6 as boolean) as est_jour_ouvre
from jours
