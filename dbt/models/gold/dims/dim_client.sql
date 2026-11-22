-- Clients, SCD 1 (un état par client). Âge et tranche d'âge calculés à la date d'arrêté (macro
-- date_arrete, défaut : 31/12 de l'exercice), jamais à la date du jour (current_date) : le
-- résultat ne dépend pas du jour d'exécution.
{%- set arrete = date_arrete() %}

with clients as (
    select
        *,
        case
            when date_naissance is not null
                then cast(extract(year from age({{ arrete }}, date_naissance)) as integer)
        end as age_au_31_12
    from {{ ref('slv_clients') }}
    where date_adhesion <= {{ date_arrete() }}
)

select
    id_client,
    id_agence,
    sexe,
    date_naissance,
    age_au_31_12,
    cast(case
        when age_au_31_12 is null then 'NON_RENSEIGNE'
        when age_au_31_12 < 26 then '18-25'
        when age_au_31_12 < 36 then '26-35'
        when age_au_31_12 < 46 then '36-45'
        when age_au_31_12 < 56 then '46-55'
        when age_au_31_12 < 66 then '56-65'
        else '66+'
    end as text) as tranche_age,
    -- NULL accepté en silver (ACCEPTER_NULL), libellé explicite en gold.
    cast(coalesce(secteur_activite, 'NON_RENSEIGNE') as text) as secteur_activite,
    date_adhesion
from clients
