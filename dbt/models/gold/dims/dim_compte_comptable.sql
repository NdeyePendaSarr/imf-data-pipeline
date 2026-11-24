-- Plan de comptes simplifié (seed plan_comptes), codes internes ; correspondances SYSCOHADA
-- indicatives. mvp = compte mouvementé au MVP (les autres sont des bonus).
select
    cast(code_compte as {{ dbt.type_string() }}) as code_compte,
    cast(libelle as {{ dbt.type_string() }}) as libelle,
    cast(nature as {{ dbt.type_string() }}) as nature,
    cast(sens_normal as {{ dbt.type_string() }}) as sens_normal,
    cast(etat as {{ dbt.type_string() }}) as etat,
    cast(rubrique as {{ dbt.type_string() }}) as rubrique,
    cast(compte_sfd as {{ dbt.type_string() }}) as compte_sfd,
    cast(compte_syscohada_equiv as {{ dbt.type_string() }}) as compte_syscohada_equiv,
    cast(statut_correspondance as {{ dbt.type_string() }}) as statut_correspondance,
    cast(mvp as boolean) as mvp,
    -- v0.5 (H8) : rubrique où classer le compte si son solde est inversé (liaisons MM et agents).
    cast(rubrique_solde_inverse as {{ dbt.type_string() }}) as rubrique_solde_inverse
from {{ ref('plan_comptes') }}
