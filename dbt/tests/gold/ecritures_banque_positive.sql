-- D19 / G13 : la banque (compte TRESO_BANQUE, toutes agences confondues, au niveau de l'IMF)
-- ne devient jamais négative en fin de journée.
with par_jour as (
    select date_ecriture, sum(debit - credit) as mouvement
    from {{ ref('fct_ecritures') }}
    where code_compte = 'TRESO_BANQUE'
    group by date_ecriture
),

cumul as (
    select date_ecriture, sum(mouvement) over (order by date_ecriture) as solde
    from par_jour
)

select * from cumul where solde < 0
