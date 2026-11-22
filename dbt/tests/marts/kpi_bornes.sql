-- paye_impute_cumule ≤ du_echu_cumule et encours_par30 ≤ encours, sur chaque ligne.
select date, id_agence, code_produit, paye_impute_cumule, du_echu_cumule, encours_par30, encours
from {{ ref('mart_kpi_portefeuille') }}
where paye_impute_cumule > du_echu_cumule or encours_par30 > encours
