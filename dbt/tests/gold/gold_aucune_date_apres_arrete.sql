-- Aucune date du gold n'est postérieure à la date d'arrêté (phase 7, lot A). Exceptions par
-- nature, hors de ce contrôle : dim_date (calendrier, exercice + 2 ans) et
-- fct_echeances.date_prevue (échéances futures planifiées).
{%- set colonnes = [
    ('dim_client', 'date_adhesion'),
    ('dim_compte_client', 'date_ouverture'),
    ('dim_credit', 'date_decaissement'),
    ('fct_ecritures', 'date_ecriture'),
    ('fct_operations', 'date_operation'),
    ('fct_remboursements', 'date_remboursement'),
    ('fct_echeances', 'date_couverture'),
    ('fct_portefeuille_quotidien', 'date'),
    ('fct_solde_compte_mensuel', 'date_situation'),
    ('mart_balance', 'date_situation'),
    ('mart_compte_resultat', 'date_situation'),
    ('mart_bilan', 'date_situation'),
    ('mart_rapprochements', 'date_situation'),
    ('mart_kpi_portefeuille', 'date'),
] %}
{% for modele, colonne in colonnes %}
select '{{ modele }}.{{ colonne }}' as colonne, max({{ colonne }}) as date_max
from {{ ref(modele) }}
having max({{ colonne }}) > {{ date_arrete() }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
