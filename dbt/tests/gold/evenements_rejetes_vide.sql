-- Aucun événement de l'exercice ne doit être rejeté par la comptabilisation (G3).
select * from {{ ref('int_evenements_rejetes') }}
