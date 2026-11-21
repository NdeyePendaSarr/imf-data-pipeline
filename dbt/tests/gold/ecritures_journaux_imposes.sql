-- Journaux imposés par le type : APPRO_CAISSE au journal VIR (D18), OUVERTURE au journal OUV.
select id_ecriture, type_evenement, code_journal
from {{ ref('fct_ecritures') }}
where (type_evenement = 'APPRO_CAISSE' and code_journal <> 'VIR')
    or (type_evenement = 'OUVERTURE' and code_journal <> 'OUV')
