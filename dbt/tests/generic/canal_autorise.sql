{#
  Test générique canal_autorise (D16) : le canal de chaque ligne doit figurer dans le seed
  canaux_autorises pour la source indiquée.

  Usage (dbt 1.12) :
      - canal_autorise:
          arguments:
            nom_source: operations

  L'argument s'appelle nom_source, pas « source » : ce nom masquerait la fonction Jinja
  source() à l'intérieur du test.

  Renvoie les lignes du modèle dont le couple (nom_source, canal) n'a pas de correspondance
  dans le seed ; le test passe s'il ne renvoie aucune ligne. Un canal NULL n'a jamais de
  correspondance : il est donc aussi signalé.
#}
{% test canal_autorise(model, column_name, nom_source) %}

select modele.*
from {{ model }} as modele
where not exists (
    select 1
    from {{ ref('canaux_autorises') }} as autorises
    where autorises.source = '{{ nom_source }}'
        and autorises.canal = modele.{{ column_name }}
)

{% endtest %}
