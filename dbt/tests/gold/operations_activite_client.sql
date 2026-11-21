-- G12 : est_activite_client est faux pour FRAIS_TENUE et seulement pour lui.
select id_operation, type_operation, est_activite_client
from {{ ref('fct_operations') }}
where est_activite_client <> (type_operation <> 'FRAIS_TENUE')
