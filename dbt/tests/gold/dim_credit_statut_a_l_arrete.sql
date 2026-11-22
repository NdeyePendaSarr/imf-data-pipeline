-- statut_a_l_arrete : EN_COURS ⇔ le crédit a une ligne dans le portefeuille (encours > 0) à la
-- date d'arrêté. À l'arrêté par défaut (31/12 de l'exercice), il est égal à statut_au_31_12.
{%- set par_defaut = var('date_arrete', '') in (none, '', var('exercice') ~ '-12-31') %}
select c.id_credit, c.statut_au_31_12, c.statut_a_l_arrete, p.id_credit as au_portefeuille
from {{ ref('dim_credit') }} as c
left join {{ ref('fct_portefeuille_quotidien') }} as p
    on p.id_credit = c.id_credit and p.date = {{ date_arrete() }}
where (c.statut_a_l_arrete = 'EN_COURS') <> (p.id_credit is not null)
{% if par_defaut %}
    or c.statut_a_l_arrete <> c.statut_au_31_12
{% endif %}
