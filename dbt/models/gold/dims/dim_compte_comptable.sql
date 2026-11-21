-- Plan de comptes simplifié (seed plan_comptes), codes internes ; correspondances SYSCOHADA
-- indicatives. mvp = compte mouvementé au MVP (les autres sont des bonus).
select
    cast(code_compte as text) as code_compte,
    cast(libelle as text) as libelle,
    cast(nature as text) as nature,
    cast(sens_normal as text) as sens_normal,
    cast(etat as text) as etat,
    cast(rubrique as text) as rubrique,
    cast(compte_sfd as text) as compte_sfd,
    cast(compte_syscohada_equiv as text) as compte_syscohada_equiv,
    cast(statut_correspondance as text) as statut_correspondance,
    cast(mvp as boolean) as mvp
from {{ ref('plan_comptes') }}
