"""Empreinte du gold : validation, lecture/écriture, comparaison."""

from pathlib import Path

import pytest

from orchestration.empreinte import (
    MD5_VIDE,
    NB_TABLES,
    Empreinte,
    ErreurEmpreinte,
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


@pytest.mark.parametrize("md5,lignes", [("", 5), (MD5_VIDE, 0), (MD5_VIDE, 3)])
def test_empreinte_vide(md5: str, lignes: int) -> None:
    jeu = _jeu()
    jeu[3] = Empreinte("table_03", lignes, md5)
    with pytest.raises(ErreurEmpreinte, match="empreinte vide : table_03"):
        valider(jeu)


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
