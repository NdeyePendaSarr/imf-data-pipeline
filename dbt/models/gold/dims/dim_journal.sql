-- Journaux comptables (seed journaux) : code, libellé, priorité et règle d'affectation.
-- Types portables (L7, essai phase 9) : dbt.type_string() = text sur PostgreSQL, string sur
-- BigQuery ; dbt.type_int() = integer / int64.
select
    cast(code_journal as {{ dbt.type_string() }}) as code_journal,
    cast(libelle as {{ dbt.type_string() }}) as libelle,
    cast(priorite as {{ dbt.type_int() }}) as priorite,
    cast(regle as {{ dbt.type_string() }}) as regle
from {{ ref('journaux') }}
