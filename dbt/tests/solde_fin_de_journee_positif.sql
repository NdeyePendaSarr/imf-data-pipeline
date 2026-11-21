-- Solde de chaque compte client en fin de journée ≥ 0 (cumul des mouvements jour par jour).
with par_jour as (
    select id_compte, date, sum(montant_signe) as mouvement_du_jour
    from {{ ref('int_mouvements_compte') }}
    group by id_compte, date
),

soldes as (
    select
        id_compte,
        date,
        sum(mouvement_du_jour) over (partition by id_compte order by date) as solde_fin_de_journee
    from par_jour
)

select * from soldes where solde_fin_de_journee < 0
