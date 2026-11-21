"""Fenêtres d'extraction incrémentale (fonctions pures, sans base de données).

Pour un run du jour J, la fenêtre d'une table est l'intervalle ouvert
]filigrane, J+1 00:00[ sur date_maj : tout ce qui a changé après le dernier extrait et
jusqu'à la fin du jour J. La borne haute dépend de J, jamais de l'horloge (pas de now()).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class Fenetre:
    """Intervalle ]debut_exclu, fin_exclue[ ; debut_exclu None : depuis l'origine."""

    debut_exclu: datetime | None
    fin_exclue: datetime

    @property
    def vide(self) -> bool:
        """Vrai si aucune date_maj ne peut tomber dans la fenêtre (jour déjà extrait)."""
        return self.debut_exclu is not None and self.debut_exclu >= self.fin_exclue

    def contient(self, instant: datetime) -> bool:
        """Vrai si `instant` appartient à la fenêtre (même règle que la requête SQL)."""
        apres_debut = self.debut_exclu is None or instant > self.debut_exclu
        return apres_debut and instant < self.fin_exclue


def fin_du_jour(jour: date) -> datetime:
    """Borne haute exclue : J+1 à 00:00:00."""
    return datetime.combine(jour + timedelta(days=1), time(0, 0, 0))


def calculer_fenetre(filigrane: datetime | None, jour: date) -> Fenetre:
    """Fenêtre d'extraction du jour J à partir du filigrane de la table."""
    return Fenetre(filigrane, fin_du_jour(jour))


def nouveau_filigrane(avant: datetime | None, max_extrait: datetime | None) -> datetime | None:
    """Filigrane après extraction : max(date_maj) extrait ; inchangé si rien n'a été extrait."""
    if max_extrait is None:
        return avant
    return max_extrait if avant is None else max(avant, max_extrait)


def jours_entre(du: date, au: date) -> list[date]:
    """Jours de `du` à `au` inclus, dans l'ordre (rattrapage jour par jour)."""
    if du > au:
        raise ValueError(f"période vide : {du.isoformat()} est après {au.isoformat()}")
    return [du + timedelta(days=n) for n in range((au - du).days + 1)]


def jours_exercice(exercice: int) -> list[date]:
    """Tous les jours d'un exercice (année civile)."""
    return jours_entre(date(exercice, 1, 1), date(exercice, 12, 31))
