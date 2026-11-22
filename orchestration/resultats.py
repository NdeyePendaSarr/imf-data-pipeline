"""Résumés et règles d'évaluation des contrôles (fonctions pures, sans base de données)."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
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
DIMANCHE = 7

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


def evaluer_volume(
    jour: date,
    nb_jour: int,
    historique: Mapping[date, int | None],
) -> Resume:
    """Contrôle de volume des opérations du jour (avertissement seulement, jamais bloquant).

    `historique` : les 4 mêmes jours de semaine précédents (J−7 à J−28), avec None pour un jour
    non ingéré. Moins de 4 semaines d'historique : pas de contrôle. Un dimanche à 0 est normal.
    Hors de [50 % ; 200 %] de la moyenne de référence : AVERTISSEMENT.
    """

    def resume(statut: str, message: str, details: dict[str, Any] | None = None) -> Resume:
        return Resume(
            "volume", jour.isoformat(), statut, message,
            lignes_chargees=nb_jour, details=details or {},
        )  # fmt: skip

    if jour.isoweekday() == DIMANCHE and nb_jour == 0:
        return resume(SUCCES, "dimanche sans opération : normal")
    valeurs = [historique.get(jour.fromordinal(jour.toordinal() - 7 * k)) for k in range(1, 5)]
    if len(historique) < VOLUME_SEMAINES_REFERENCE or any(v is None for v in valeurs):
        return resume(SUCCES, "historique de moins de 4 semaines : pas de contrôle")
    moyenne = sum(v for v in valeurs if v is not None) / VOLUME_SEMAINES_REFERENCE
    ratio = (nb_jour / moyenne) if moyenne else (float("inf") if nb_jour else 1.0)
    details = {"moyenne_reference": round(moyenne, 2), "ratio": round(ratio, 4)}
    if VOLUME_RATIO_MIN <= ratio <= VOLUME_RATIO_MAX:
        message = f"{nb_jour} opérations, {ratio:.0%} de la moyenne des 4 mêmes jours"
        return resume(SUCCES, message, details)
    message = (
        f"volume inhabituel : {nb_jour} opérations pour une moyenne de {moyenne:.1f} "
        f"(hors de [50 % ; 200 %])"
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
