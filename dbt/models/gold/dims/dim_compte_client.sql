-- Comptes des clients (épargne ou courant). À ne pas confondre avec dim_compte_comptable.
select
    id_compte,
    id_client,
    type_compte,
    statut,
    date_ouverture
from {{ ref('slv_comptes') }}
