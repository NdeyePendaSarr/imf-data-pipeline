-- H1 : les fins de mois du dimanche de l'exercice 2025 (31/08 et 30/11) existent dans le
-- portefeuille. Renvoie la date manquante, s'il y en a une.
{%- set annee = var('exercice') %}
-- union all de select : SQL standard ((values …) as attendu (…) n'existe pas en BigQuery).
select attendu.date
from (
    select cast('{{ annee }}-08-31' as date) as date
    union all select cast('{{ annee }}-11-30' as date)
) as attendu
where attendu.date <= {{ date_arrete() }}  -- seulement si la date est passée à l'arrêté
and not exists (
    select 1 from {{ ref('fct_portefeuille_quotidien') }} as p where p.date = attendu.date
)
