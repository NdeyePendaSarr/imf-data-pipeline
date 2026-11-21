"""Référentiels du générateur : agences, secteurs, prénoms et noms sénégalais."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DefinitionAgence:
    """Agence de SenFinance Microcrédit (la clé sert d'index dans config.py)."""

    cle: str
    nom: str
    ville: str
    region: str
    type_agence: str


SIEGE = "SIEGE"
REGIONALE = "REGIONALE"

AGENCES: tuple[DefinitionAgence, ...] = (
    DefinitionAgence("SIEGE", "Siège", "Dakar", "Dakar", SIEGE),
    DefinitionAgence("DAKAR", "Agence de Dakar", "Dakar", "Dakar", REGIONALE),
    DefinitionAgence("THIES", "Agence de Thiès", "Thiès", "Thiès", REGIONALE),
    DefinitionAgence("KAOLACK", "Agence de Kaolack", "Kaolack", "Kaolack", REGIONALE),
    DefinitionAgence(
        "SAINT_LOUIS", "Agence de Saint-Louis", "Saint-Louis", "Saint-Louis", REGIONALE
    ),
    DefinitionAgence("ZIGUINCHOR", "Agence de Ziguinchor", "Ziguinchor", "Ziguinchor", REGIONALE),
)

# Secteurs d'activité des clients (poids dans config.POIDS_SECTEURS).
SECTEURS: tuple[str, ...] = (
    "COMMERCE",
    "AGRICULTURE",
    "ELEVAGE",
    "PECHE",
    "ARTISANAT",
    "TRANSPORT",
    "SERVICES",
)

PRENOMS_FEMMES: tuple[str, ...] = (
    "Adama", "Aïssatou", "Aminata", "Astou", "Awa", "Bineta", "Coumba", "Dieynaba",
    "Fanta", "Fatou", "Khady", "Kiné", "Maïmouna", "Mame", "Mariama", "Nafissatou",
    "Ndella", "Ndeye", "Oumou", "Penda", "Ramatoulaye", "Rokhaya", "Seynabou", "Sokhna",
    "Yacine",
)  # fmt: skip

PRENOMS_HOMMES: tuple[str, ...] = (
    "Abdoulaye", "Aliou", "Alioune", "Amadou", "Assane", "Babacar", "Boubacar", "Cheikh",
    "Demba", "Djibril", "El Hadji", "Ibrahima", "Lamine", "Malick", "Mamadou", "Modou",
    "Mouhamed", "Moussa", "Omar", "Ousmane", "Pape", "Saliou", "Samba", "Serigne",
    "Souleymane",
)  # fmt: skip

NOMS: tuple[str, ...] = (
    "Ba", "Badji", "Camara", "Ciss", "Cissé", "Coly", "Diagne", "Diallo", "Diatta", "Dieng",
    "Diop", "Diouf", "Fall", "Faye", "Gueye", "Ka", "Kane", "Lo", "Mané", "Mbaye",
    "Mbengue", "Ndao", "Ndiaye", "Niang", "Sagna", "Sall", "Sarr", "Seck", "Sène", "Sow",
    "Sy", "Thiam", "Touré", "Wade",
)  # fmt: skip
