-- Remboursements (imf_ops) : dernière version par remboursement (S8) et motif d'écart.
with versions as (
    select
        *,
        row_number() over (
            partition by id_remboursement order by date_maj desc, _charge_le desc
        ) as rang_version
    from {{ source('bronze', 'ops_remboursements') }}
),

credits as (
    select id_credit, date_decaissement from {{ ref('stg_credits') }}
),

derniere as (
    select
        id_remboursement,
        id_credit,
        date_remboursement,
        montant_paye,
        part_capital,
        part_interets,
        penalites,
        {{ standardiser('canal') }} as canal,
        date_maj,
        _id_run,
        _source,
        _num_ligne
    from versions
    where rang_version = 1
)

select
    derniere.*,
    -- Un seul motif par ligne, par ordre de priorité (S6).
    case
        when least(montant_paye, part_capital, part_interets, penalites) < 0 then 'MONTANT_NEGATIF'
        when not exists (
            select 1 from {{ ref('canaux_autorises') }} as a
            where a.source = 'remboursements' and a.canal = derniere.canal
        ) then 'CANAL_NON_AUTORISE'
        -- Un remboursement ne peut pas précéder le décaissement de son crédit.
        when derniere.date_remboursement < credits.date_decaissement then 'DATE_INCOHERENTE'
        when montant_paye <> part_capital + part_interets + penalites then 'MONTANT_PAYE_INCOHERENT'
    end as motif_ecart
from derniere
left join credits on credits.id_credit = derniere.id_credit
