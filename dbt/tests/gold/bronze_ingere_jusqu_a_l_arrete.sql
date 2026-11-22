-- Bloquant : le bronze doit être ingéré au moins jusqu'à la date d'arrêté. Sinon les marts
-- seraient calculés sur une période incomplète sans que rien ne le signale.
select max(jour) as dernier_jour_ingere, {{ date_arrete() }} as date_arrete
from {{ source('bronze', '_ingestions') }}
having max(jour) is null or max(jour) < {{ date_arrete() }}
