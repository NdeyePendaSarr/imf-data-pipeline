-- D14 : la caisse de chaque agence (compte TRESO_CAISSE, débit − crédit cumulés) ne devient
-- jamais négative en fin de journée.
with par_jour as (
    select id_agence, date_ecriture, sum(debit - credit) as mouvement
    from {{ ref('fct_ecritures') }}
    where code_compte = 'TRESO_CAISSE'
    group by id_agence, date_ecriture
),

cumul as (
    select
        id_agence,
        date_ecriture,
        sum(mouvement) over (partition by id_agence order by date_ecriture) as solde
    from par_jour
)

select * from cumul where solde < 0
