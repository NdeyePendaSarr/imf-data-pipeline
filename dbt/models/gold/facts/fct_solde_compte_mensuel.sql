-- Solde de chaque compte client à chaque fin de mois de l'exercice (12 dates), pour les comptes
-- ouverts à cette date : cumul des mouvements de int_mouvements_compte jusqu'à la fin du mois.
with fins_de_mois as (
    select date as date_fin_mois
    from {{ ref('dim_date') }}
    where dans_exercice and est_fin_de_mois
),

comptes as (
    select c.id_compte, c.id_client, cl.id_agence, c.type_compte, c.date_ouverture
    from {{ ref('dim_compte_client') }} as c
    inner join {{ ref('dim_client') }} as cl on cl.id_client = c.id_client
),

mouvements_par_mois as (
    select id_compte, (date_trunc('month', date) + interval '1 month - 1 day')::date as date_fin_mois,
        sum(montant_signe) as mouvement
    from {{ ref('int_mouvements_compte') }}
    group by 1, 2
)

select
    cast(f.date_fin_mois as date) as date_fin_mois,
    cast(c.id_compte as text) as id_compte,
    cast(c.id_client as text) as id_client,
    cast(c.id_agence as text) as id_agence,
    cast(c.type_compte as text) as type_compte,
    cast(coalesce(sum(m.mouvement), 0) as bigint) as solde
from comptes as c
inner join fins_de_mois as f on f.date_fin_mois >= c.date_ouverture
left join mouvements_par_mois as m on m.id_compte = c.id_compte and m.date_fin_mois <= f.date_fin_mois
group by f.date_fin_mois, c.id_compte, c.id_client, c.id_agence, c.type_compte
