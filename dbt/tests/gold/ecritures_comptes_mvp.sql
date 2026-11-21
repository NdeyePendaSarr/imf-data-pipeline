-- Chaque ligne mouvemente un compte du plan utilisé au MVP.
select e.id_ecriture, e.num_ligne, e.code_compte
from {{ ref('fct_ecritures') }} as e
left join {{ ref('dim_compte_comptable') }} as c on c.code_compte = e.code_compte and c.mvp
where c.code_compte is null
