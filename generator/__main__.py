"""Point d'entrée : uv run python -m generator [options]."""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generator.anomalies import Brut, injecter
from generator.config import Config
from generator.ecriture import ecrire_sorties
from generator.simulation import Verite, simuler


@dataclass(frozen=True)
class Generation:
    """Résultat d'une génération : configuration, vérité, sorties brutes et manifeste."""

    config: Config
    verite: Verite
    brut: Brut
    manifeste: dict[str, Any]


def generer(config: Config) -> Generation:
    """Simule la vérité, injecte les anomalies et écrit data/ (sans base de données)."""
    verite = simuler(config)
    brut = injecter(verite, config)
    manifeste = ecrire_sorties(verite, brut, config)
    return Generation(config, verite, brut, manifeste)


def lire_arguments(arguments: list[str] | None = None) -> Config:
    """Analyse la ligne de commande et renvoie la configuration."""
    defaut = Config()
    parser = argparse.ArgumentParser(
        prog="python -m generator",
        description="Génère les données fictives de SenFinance Microcrédit.",
    )
    parser.add_argument("--exercice", type=int, default=defaut.exercice, help="année civile")
    parser.add_argument("--clients", type=int, default=defaut.nb_clients, help="nombre de clients")
    parser.add_argument("--credits", type=int, default=defaut.nb_credits, help="nombre de crédits")
    parser.add_argument("--seed", type=int, default=defaut.seed, help="graine aléatoire")
    parser.add_argument(
        "--taux-anomalies", type=float, default=defaut.taux_anomalies, help="taux par type"
    )
    parser.add_argument("--sortie", type=Path, default=defaut.sortie, help="dossier de sortie")
    ns = parser.parse_args(arguments)
    config = Config(
        exercice=ns.exercice,
        nb_clients=ns.clients,
        nb_credits=ns.credits,
        seed=ns.seed,
        taux_anomalies=ns.taux_anomalies,
        sortie=ns.sortie,
    )
    return config


def main(arguments: list[str] | None = None) -> int:
    """Exécute le générateur et affiche un résumé."""
    config = lire_arguments(arguments)
    try:
        generation = generer(config)
    except ValueError as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    lignes = generation.manifeste["lignes"]
    indicateurs = generation.manifeste["indicateurs"]
    print(f"data/ écrit dans {config.sortie} : {len(generation.manifeste['fichiers'])} fichiers")
    for table, nombre in sorted(lignes["brut"].items()):
        print(f"  {table:<22} {nombre:>8}")
    print(f"PAR 30 au 31/12 : {indicateurs['par30_31_12']:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
