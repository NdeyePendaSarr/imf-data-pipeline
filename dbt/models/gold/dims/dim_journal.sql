-- Journaux comptables (seed journaux) : code, libellé, priorité et règle d'affectation.
select
    cast(code_journal as text) as code_journal,
    cast(libelle as text) as libelle,
    cast(priorite as integer) as priorite,
    cast(regle as text) as regle
from {{ ref('journaux') }}
