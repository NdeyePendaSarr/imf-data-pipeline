-- Même identifiant, contenu différent : ce n'est pas un doublon exact (S7) et le silver
-- garderait une version arbitraire. Doit renvoyer 0 ligne.
{%- set sources = [
    ('stg_agences', 'id_agence', ['nom', 'ville', 'region', 'type_agence']),
    ('stg_ouverture', 'id_ligne', ['date_ouverture', 'montant']),
    ('stg_operations', 'id_operation', ['id_compte', 'id_agence', 'date_operation', 'type_operation', 'canal', 'montant']),
    ('stg_charges', 'id_charge', ['id_agence', 'date_charge', 'categorie', 'canal', 'montant']),
    ('stg_appro_caisse', 'id_appro', ['id_agence', 'date_appro', 'montant']),
] %}
{#- Versions distinctes par identifiant : select distinct puis comptage (SQL standard, L6) ;
    count(distinct (a, b, …)) sur une ligne n'existe qu'en PostgreSQL. #}
{% for modele, identifiant, colonnes in sources %}
select '{{ modele }}' as modele, id_ligne, count(*) as versions
from (
    select distinct {{ identifiant }} as id_ligne, {{ colonnes | join(', ') }}
    from {{ ref(modele) }}
) as distinctes
group by id_ligne
having count(*) > 1
{% if not loop.last %}union all{% endif %}
{% endfor %}
