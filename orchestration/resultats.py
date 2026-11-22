"""Résumés et règles d'évaluation des contrôles (fonctions pures, sans base de données)."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

# Statuts d'une étape (colonne audit.audit_runs.statut).
SUCCES = "SUCCES"
AVERTISSEMENT = "AVERTISSEMENT"
ECHEC_CONTROLE = "ECHEC_CONTROLE"
ECHEC_TECHNIQUE = "ECHEC_TECHNIQUE"
NON_EXECUTE = "NON_EXECUTE"

# Codes de sortie du CLI.
CODE_SUCCES = 0
CODE_ECHEC_CONTROLE = 3
CODE_ERREUR_TECHNIQUE = 1

CODES = {
    SUCCES: CODE_SUCCES,
    AVERTISSEMENT: CODE_SUCCES,
    ECHEC_CONTROLE: CODE_ECHEC_CONTROLE,
    ECHEC_TECHNIQUE: CODE_ERREUR_TECHNIQUE,
}

# Contrôle de volume : plage acceptée du ratio opérations du jour / moyenne de référence.
VOLUME_RATIO_MIN = 0.5
VOLUME_RATIO_MAX = 2.0
VOLUME_SEMAINES_REFERENCE = 4
# Jours ordinaires servant au facteur de tendance : 7 pour un jour ordinaire, 28 pour une fin
# de mois (croissance du mois écoulé).
VOLUME_JOURS_TENDANCE = 7
VOLUME_JOURS_TENDANCE_FIN_DE_MOIS = 28
DIMANCHE = 7
# Jours ouvrés du guichet et des agents : lundi à samedi, sans jours fériés (cadrage, I1).
JOURS_OUVRES = frozenset({1, 2, 3, 4, 5, 6})

# Messages dbt d'une base injoignable : un nœud en erreur pour cette raison est une panne
# technique (relançable), pas un échec de contrôle.
MESSAGES_CONNEXION = (
    "could not connect",
    "connection refused",
    "connection to server",
    "server closed the connection",
    "terminating connection",
    "could not translate host name",
)


@dataclass(frozen=True)
class Resume:
    """Résumé d'une commande, imprimé en JSON sur la dernière ligne de stdout."""

    commande: str
    date: str
    statut: str
    message: str = ""
    lignes_chargees: int | None = None
    nb_pass: int | None = None
    nb_warn: int | None = None
    nb_error: int | None = None
    nb_skip: int | None = None
    noeuds_en_echec: list[str] = field(default_factory=list)
    noeuds_sautes: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def code(self) -> int:
        """Code de sortie du CLI correspondant au statut."""
        return CODES[self.statut]

    def json(self) -> str:
        """Résumé JSON sur une seule ligne (clés triées, déterministe)."""
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, default=str)


def evaluer_run_results(jour: date, code_dbt: int, run_results: Mapping[str, Any] | None) -> Resume:
    """Évalue un dbt build à partir de son code de sortie et de run_results.json.

    Un nœud en error, fail ou skipped est un échec de contrôle (le gold n'est pas à jour, ne pas
    relancer). Un code dbt 2 (erreur non gérée), un run_results.json absent, ou des nœuds en
    erreur parce que la base est injoignable sont une erreur technique (relançable). Un test en
    warn donne un AVERTISSEMENT.
    """
    if code_dbt == 2 or run_results is None:
        return Resume(
            "dbt",
            jour.isoformat(),
            ECHEC_TECHNIQUE,
            f"dbt build : code {code_dbt}"
            + (", run_results.json absent" if run_results is None else ""),
        )
    resultats: Sequence[Mapping[str, Any]] = run_results.get("results", [])
    statuts = [str(r.get("status", "")).lower() for r in resultats]
    en_echec = sorted(
        str(r["unique_id"])
        for r, s in zip(resultats, statuts, strict=True)
        if s in ("error", "fail")
    )
    sautes = sorted(
        str(r["unique_id"]) for r, s in zip(resultats, statuts, strict=True) if s == "skipped"
    )
    nb_pass = sum(1 for s in statuts if s in ("success", "pass"))
    nb_warn = sum(1 for s in statuts if s == "warn")
    messages_erreur = [
        str(r.get("message") or "").lower()
        for r, s in zip(resultats, statuts, strict=True)
        if s == "error"
    ]
    base_injoignable = bool(messages_erreur) and all(
        any(motif in m for motif in MESSAGES_CONNEXION) for m in messages_erreur
    )
    if base_injoignable:
        statut = ECHEC_TECHNIQUE
        message = f"base injoignable pendant dbt build ({len(messages_erreur)} nœud(s) en erreur)"
    elif en_echec or sautes:
        statut = ECHEC_CONTROLE
        message = f"{len(en_echec)} nœud(s) en échec, {len(sautes)} nœud(s) sauté(s)"
    elif code_dbt != 0:
        statut = ECHEC_TECHNIQUE
        message = f"dbt build : code {code_dbt} sans nœud en échec"
    else:
        statut = AVERTISSEMENT if nb_warn else SUCCES
        message = f"{nb_pass} PASS, {nb_warn} WARN"
    return Resume(
        "dbt",
        jour.isoformat(),
        statut,
        message,
        nb_pass=nb_pass,
        nb_warn=nb_warn,
        nb_error=len(en_echec),
        nb_skip=len(sautes),
        noeuds_en_echec=en_echec,
        noeuds_sautes=sautes,
    )


def est_dernier_jour_ouvre(jour: date) -> bool:
    """Vrai pour le dernier jour ouvré (lundi à samedi) de son mois."""
    if jour.isoweekday() not in JOURS_OUVRES:
        return False
    suivant = jour + timedelta(days=1)
    while suivant.isoweekday() not in JOURS_OUVRES:
        suivant += timedelta(days=1)
    return suivant.month != jour.month


class _HistoriqueIncomplet(Exception):
    """Un jour nécessaire au calcul n'a pas été ingéré."""


def _volume(volumes: Mapping[date, int | None], jour: date) -> int:
    valeur = volumes.get(jour)
    if valeur is None:
        raise _HistoriqueIncomplet(jour.isoformat())
    return valeur


def _ordinaires(volumes: Mapping[date, int | None], fin: date, nb_jours: int) -> float:
    """Opérations par jour ordinaire sur les nb_jours précédant `fin` (exclu), derniers jours
    ouvrés du mois exclus. Une moyenne et non une somme : une fenêtre qui contient une fin de
    mois compte un jour de moins, sans biaiser le facteur de tendance."""
    jours = [fin - timedelta(days=i) for i in range(1, nb_jours + 1)]
    valeurs = [_volume(volumes, j) for j in jours if not est_dernier_jour_ouvre(j)]
    return sum(valeurs) / len(valeurs)


def _reference_ordinaire(volumes: Mapping[date, int | None], jour: date) -> tuple[float, float]:
    """Moyenne des 4 mêmes jours de semaine précédents, fins de mois exclues, et facteur de
    tendance : 7 derniers jours ordinaires / moyenne des mêmes 7 jours décalés de 1 à 4 semaines."""
    references: list[int] = []
    candidat = jour
    while len(references) < VOLUME_SEMAINES_REFERENCE:
        candidat -= timedelta(days=7)
        if candidat.year != jour.year:
            raise _HistoriqueIncomplet("moins de 4 semaines dans l'exercice")
        if not est_dernier_jour_ouvre(candidat):
            references.append(_volume(volumes, candidat))
    recent = _ordinaires(volumes, jour, VOLUME_JOURS_TENDANCE)
    semaines = [
        _ordinaires(volumes, jour - timedelta(days=7 * k), VOLUME_JOURS_TENDANCE)
        for k in range(1, VOLUME_SEMAINES_REFERENCE + 1)
    ]
    base = sum(semaines) / len(semaines)
    return sum(references) / len(references), (recent / base if base else 1.0)


def _reference_fin_de_mois(volumes: Mapping[date, int | None], jour: date) -> tuple[float, float]:
    """Fin de mois précédente et facteur de tendance : 28 derniers jours ordinaires / les 28
    jours ordinaires avant la fin de mois précédente."""
    candidat = jour.replace(day=1) - timedelta(days=1)
    while not est_dernier_jour_ouvre(candidat):
        candidat -= timedelta(days=1)
    if candidat.year != jour.year:
        raise _HistoriqueIncomplet("aucune fin de mois précédente dans l'exercice")
    precedente = _volume(volumes, candidat)
    recent = _ordinaires(volumes, jour, VOLUME_JOURS_TENDANCE_FIN_DE_MOIS)
    base = _ordinaires(volumes, candidat, VOLUME_JOURS_TENDANCE_FIN_DE_MOIS)
    return float(precedente), (recent / base if base else 1.0)


def evaluer_volume(jour: date, volumes: Mapping[date, int | None]) -> Resume:
    """Contrôle de volume des opérations du jour (avertissement seulement, jamais bloquant).

    `volumes` : opérations par jour de l'exercice jusqu'à J inclus (None ou absent = jour non
    ingéré). La référence suit la croissance du portefeuille :
    - jour ordinaire : moyenne des 4 mêmes jours de semaine précédents (fins de mois exclues)
      × facteur de tendance sur 7 jours ;
    - dernier jour ouvré du mois : fin de mois précédente × facteur de tendance sur 28 jours.
    Hors de [50 % ; 200 %] de la référence : AVERTISSEMENT. Historique insuffisant (moins de
    4 semaines, aucune fin de mois précédente, jour non ingéré) : pas de contrôle. Un dimanche
    à 0 est normal.
    """
    nb_jour = volumes.get(jour) or 0

    def resume(statut: str, message: str, details: dict[str, Any] | None = None) -> Resume:
        return Resume(
            "volume", jour.isoformat(), statut, message,
            lignes_chargees=nb_jour, details=details or {},
        )  # fmt: skip

    if jour.isoweekday() == DIMANCHE and nb_jour == 0:
        return resume(SUCCES, "dimanche sans opération : normal")
    fin_de_mois = est_dernier_jour_ouvre(jour)
    try:
        if fin_de_mois:
            base, facteur = _reference_fin_de_mois(volumes, jour)
        else:
            base, facteur = _reference_ordinaire(volumes, jour)
    except _HistoriqueIncomplet as manque:
        return resume(SUCCES, f"historique insuffisant ({manque}) : pas de contrôle")
    reference = base * facteur
    ratio = (nb_jour / reference) if reference else (float("inf") if nb_jour else 1.0)
    nature = "fin de mois" if fin_de_mois else "jour ordinaire"
    details = {
        "nature": nature,
        "reference_brute": round(base, 2),
        "facteur_tendance": round(facteur, 4),
        "reference": round(reference, 2),
        "ratio": round(ratio, 4),
    }
    if VOLUME_RATIO_MIN <= ratio <= VOLUME_RATIO_MAX:
        message = f"{nb_jour} opérations, {ratio:.0%} de la référence ({nature})"
        return resume(SUCCES, message, details)
    message = (
        f"volume inhabituel ({nature}) : {nb_jour} opérations pour une référence de "
        f"{reference:.1f}, soit {ratio:.0%} (hors de [50 % ; 200 %])"
    )
    return resume(AVERTISSEMENT, message, details)


def evaluer_completude(
    jour: date, attendu: Mapping[str, int], charge: Mapping[str, int], jour_ingere: bool
) -> Resume:
    """Complétude du bronze au jour J : lignes chargées = lignes attendues, fichier par fichier.

    `attendu` : lignes déclarées par le manifeste (CSV) ou présentes en landing (imf_ops) ;
    `charge` : lignes présentes en bronze pour ce fichier (_source). Un rejeu idempotent
    (IGNORE) compte comme chargé : les lignes du premier chargement sont en bronze.
    """
    if not jour_ingere:
        return Resume(
            "completude", jour.isoformat(), ECHEC_CONTROLE, "jour absent de bronze._ingestions"
        )
    ecarts = {
        chemin: {"attendu": n, "charge": charge.get(chemin, 0)}
        for chemin, n in sorted(attendu.items())
        if charge.get(chemin, 0) != n
    }
    total = sum(charge.get(chemin, 0) for chemin in attendu)
    if ecarts:
        message = f"{len(ecarts)} fichier(s) incomplet(s) en bronze"
        return Resume(
            "completude", jour.isoformat(), ECHEC_CONTROLE, message,
            lignes_chargees=total, details={"ecarts": ecarts},
        )  # fmt: skip
    message = f"{len(attendu)} fichier(s) complet(s), {total} lignes"
    return Resume("completude", jour.isoformat(), SUCCES, message, lignes_chargees=total)


def statut_global(statuts: Mapping[str, str | None]) -> str:
    """Statut du run (ligne etape = RUN) à partir du statut de chaque étape (None = sans résumé)."""
    valeurs = [s or NON_EXECUTE for s in statuts.values()]
    for statut in (ECHEC_CONTROLE, ECHEC_TECHNIQUE, NON_EXECUTE, AVERTISSEMENT):
        if statut in valeurs:
            return statut
    return SUCCES
