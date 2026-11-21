-- Même identifiant, contenu différent : ce n'est pas un doublon exact (S7) et le silver
-- garderait une version arbitraire. Doit renvoyer 0 ligne.
{%- set sources = [
    ('stg_agences', 'id_agence', ['nom', 'ville', 'region', 'type_agence']),
    ('stg_ouverture', 'id_ligne', ['date_ouverture', 'montant']),
    ('stg_operations', 'id_operation', ['id_compte', 'id_agence', 'date_operation', 'type_operation', 'canal', 'montant']),
    ('stg_charges', 'id_charge', ['id_agence', 'date_charge', 'categorie', 'canal', 'montant']),
    ('stg_appro_caisse', 'id_appro', ['id_agence', 'date_appro', 'montant']),
] %}
{% for modele, identifiant, colonnes in sources %}
select '{{ modele }}' as modele, {{ identifiant }} as id_ligne, count(distinct ({{ colonnes | join(', ') }})) as versions
from {{ ref(modele) }}
group by {{ identifiant }}
having count(distinct ({{ colonnes | join(', ') }})) > 1
{% if not loop.last %}union all{% endif %}
{% endfor %}
