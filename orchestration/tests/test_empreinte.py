"""Empreinte du gold : validation, lecture/écriture, comparaison."""

from pathlib import Path
from typing import Any

import pytest

from orchestration.empreinte import (
    MD5_VIDE,
    NB_TABLES,
    VIDE,
    Empreinte,
    ErreurEmpreinte,
    calculer,
    comparer,
    ecrire,
    lire,
    main,
    valider,
)


def _jeu(n: int = NB_TABLES) -> list[Empreinte]:
    return [Empreinte(f"table_{i:02}", 10 + i, f"{i:032x}") for i in range(n)]


def test_dix_neuf_tables_valides() -> None:
    valider(_jeu())


@pytest.mark.parametrize("n", [18, 20])
def test_nombre_de_tables_different(n: int) -> None:
    with pytest.raises(ErreurEmpreinte, match=f"{n} table"):
        valider(_jeu(n))


@pytest.mark.parametrize(
    ("md5", "lignes"),
    [
        ("", 5),
        (MD5_VIDE, 3),
        (MD5_VIDE, 0),
        (VIDE, 3),
        ("abc", 3),
        ("z" * 32, 3),
        (f"{1:032x}", 0),
    ],
    ids=[
        "absente", "md5_chaine_vide", "md5_chaine_vide_a_0_ligne", "vide_avec_lignes",
        "trop_courte", "non_hexa", "md5_sur_table_a_0_ligne",
    ],
)  # fmt: skip
def test_sortie_cassee_refusee(md5: str, lignes: int) -> None:
    jeu = _jeu()
    jeu[3] = Empreinte("table_03", lignes, md5)
    with pytest.raises(ErreurEmpreinte, match="empreinte cassée : table_03"):
        valider(jeu)


def test_table_legitimement_vide_acceptee(tmp_path: Path) -> None:
    """Ex. mart_kpi_portefeuille à l'arrêté du 15/01, avant la première fin de mois."""
    jeu = _jeu()
    jeu[3] = Empreinte("mart_kpi_portefeuille", 0, VIDE)
    valider(jeu)
    fichier = tmp_path / "e.txt"
    ecrire(jeu, fichier)
    assert "mart_kpi_portefeuille 0 VIDE" in fichier.read_text(encoding="utf-8")
    assert lire(fichier) == jeu


class _Connexion:
    """Connexion factice : liste des tables, puis (lignes, md5) de chacune."""

    def __init__(self, tables: dict[str, tuple[int, str]]) -> None:
        self.tables = tables
        self.resultat: Any = None

    def execute(self, requete: Any, parametres: Any = None) -> "_Connexion":
        texte = requete if isinstance(requete, str) else repr(requete)
        if "pg_tables" in texte:
            self.resultat = [(t,) for t in sorted(self.tables)]
        else:
            table = next(t for t in self.tables if f"'{t}'" in texte)
            self.resultat = [self.tables[table]]
        return self

    def fetchall(self) -> Any:
        return self.resultat

    def fetchone(self) -> Any:
        return self.resultat[0]


def test_calcul_note_vide_une_table_sans_ligne() -> None:
    conn = _Connexion({"fct_a": (4, "a" * 32), "mart_kpi_portefeuille": (0, MD5_VIDE)})
    assert calculer(conn) == [  # type: ignore[arg-type]
        Empreinte("fct_a", 4, "a" * 32),
        Empreinte("mart_kpi_portefeuille", 0, VIDE),
    ]


def test_ecriture_puis_lecture(tmp_path: Path) -> None:
    fichier = tmp_path / "sous" / "reference.txt"
    ecrire(_jeu(), fichier)
    assert lire(fichier) == _jeu()


def test_fichier_illisible(tmp_path: Path) -> None:
    fichier = tmp_path / "e.txt"
    fichier.write_text("CREATE TABLE\n", encoding="utf-8")
    with pytest.raises(ErreurEmpreinte, match="illisible"):
        lire(fichier)


def test_fichier_vide_refuse(tmp_path: Path) -> None:
    """Le piège du lot C : deux sorties vides ne doivent jamais passer pour identiques."""
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("", encoding="utf-8")
    b.write_text("", encoding="utf-8")
    assert main(["comparer", str(a), str(b)]) == 1


def test_comparaison(tmp_path: Path) -> None:
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    ecrire(_jeu(), a)
    ecrire(_jeu(), b)
    assert comparer(lire(a), lire(b)) == []
    assert main(["comparer", str(a), str(b)]) == 0
    modifie = _jeu()
    modifie[7] = Empreinte("table_07", 17, "f" * 32)
    ecrire(modifie, b)
    assert comparer(lire(a), lire(b)) == [f"table_07 : 17 {7:032x} ≠ 17 {'f' * 32}"]
    assert main(["comparer", str(a), str(b)]) == 1
