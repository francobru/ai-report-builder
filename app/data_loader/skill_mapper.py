"""Skill name extraction and campaign mapping.

Handles filenames like:
    'Turnos PM Estudios_jun26.csv'  \u2192 skill 'Turnos PM Estudios'  \u2192 campaign 'Turnos'
    'PM Consultas_may26.csv'        \u2192 skill 'PM Consultas'        \u2192 campaign 'Plan M\u00e9dico'
    'Conmutador_jun26.csv'          \u2192 skill 'Conmutador'          \u2192 campaign 'Conmutador'
"""

from __future__ import annotations

import re


# ======================================================================
# Month suffixes (Spanish abbreviations used in filenames)
# ======================================================================
# Accepts BOTH the 3-letter abbreviation and the full Spanish month name,
# with or without an underscore/space separator:
#     "PM Consultas_jul26"        -> "PM Consultas"
#     "0800 coca cola Junio26"    -> "0800 coca cola"
#     "Laboratorio_Julio2026"     -> "Laboratorio"
# Full names are listed first so the regex prefers the longest match.
_MONTH_WORDS = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    "septiembre|setiembre|octubre|noviembre|diciembre|"
    "ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic"
)

_MONTH_PATTERN = re.compile(
    r"[_ -]*(" + _MONTH_WORDS + r")[_ -]*(\d{2,4})$",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "ene": ("Enero", 1), "enero": ("Enero", 1),
    "feb": ("Febrero", 2), "febrero": ("Febrero", 2),
    "mar": ("Marzo", 3), "marzo": ("Marzo", 3),
    "abr": ("Abril", 4), "abril": ("Abril", 4),
    "may": ("Mayo", 5), "mayo": ("Mayo", 5),
    "jun": ("Junio", 6), "junio": ("Junio", 6),
    "jul": ("Julio", 7), "julio": ("Julio", 7),
    "ago": ("Agosto", 8), "agosto": ("Agosto", 8),
    "sep": ("Septiembre", 9), "set": ("Septiembre", 9),
    "septiembre": ("Septiembre", 9), "setiembre": ("Septiembre", 9),
    "oct": ("Octubre", 10), "octubre": ("Octubre", 10),
    "nov": ("Noviembre", 11), "noviembre": ("Noviembre", 11),
    "dic": ("Diciembre", 12), "diciembre": ("Diciembre", 12),
}


# ======================================================================
# Campaign \u2192 Skills mapping
# ======================================================================
# Keys are campaign names as shown in the report.
# Values are lists of skill names as they appear in CSV filenames
# (case-insensitive matching).

CAMPAIGN_MAPPING: dict[str, list[str]] = {
    "Turnos": [
        "Turnos Estudios",
        "Turnos PM Estudios",
        "Turno Consulta",
        "Turnos PM Consulta",
        "Gipfel Cober",
        "Gipfel PM",
        "Donacion",
        "Donaci\u00f3n",
        "0800 Onco",
        "Osde 210",
        "TelePerfomance",
        "TelePerf Cons",
        "TelePerf PM Cons",
    ],
    "Conmutador": [
        "Conmutador",
        "Busqueda Personas",
        "B\u00fasqueda Personas",
        "Camilleros",
        "Sede Caballito",
        "RechazoComm",
        "RechazoConm",
    ],
    "Plan M\u00e9dico": [
        "PM Consultas",
        "0800 Coca Cola",
    ],
    "Portal": [
        "Portal Digital",
        "Portal Paciente",
    ],
    "Agendas": [
        "Agendas Medicas",
        "Agendas m\u00e9dicas",
    ],
    "Camp HA": [
        "Camp HA",
    ],
}

# Build reverse lookup: normalized skill name \u2192 campaign name
_SKILL_TO_CAMPAIGN: dict[str, str] = {}
for _camp, _skills in CAMPAIGN_MAPPING.items():
    for _sk in _skills:
        _SKILL_TO_CAMPAIGN[_sk.lower().strip()] = _camp

# Gipfel skills (used for "sin Gipfel" filter)
GIPFEL_SKILLS = {"gipfel cober", "gipfel pm"}

# Campaign display order (as in the report)
CAMPAIGN_ORDER = ["Conmutador", "Plan M\u00e9dico", "Portal", "Turnos", "Agendas"]


# ======================================================================
# Public API
# ======================================================================

def canonical_skill_name(name: str) -> str:
    """Return the canonical spelling of a known skill.

    Filenames vary in capitalisation ("0800 coca cola" vs "0800 Coca Cola"),
    which would otherwise make the same skill look like two different ones
    when comparing two months. Unknown skills are returned unchanged.
    """
    key = name.lower().strip()
    for camp_skills in CAMPAIGN_MAPPING.values():
        for known in camp_skills:
            if known.lower() == key:
                return known
    return name


def extract_skill_name(filename: str) -> str:
    """Extract the skill name from a CSV filename.

    Examples::

        'Turnos PM Estudios_jun26.csv'  \u2192 'Turnos PM Estudios'
        'PM Consultas_may26.csv'        \u2192 'PM Consultas'
        'PM_Consultas_may26.csv'        \u2192 'PM Consultas'
        'Conmutador_jun26'              \u2192 'Conmutador'
    """
    # Remove extension
    name = filename
    if name.lower().endswith(".csv"):
        name = name[:-4]

    # Windows adds " (1)" to duplicate downloads; drop it before anything else
    name = re.sub(r"\s*\(\d+\)\s*$", "", name)

    # Remove month-year suffix. Applied twice so "PM Consultas_jul26 copia"
    # style leftovers still resolve once the trailing word is gone.
    name = _MONTH_PATTERN.sub("", name)
    name = re.sub(r"[_ -]+(copia|copy|final|v\d+)$", "", name, flags=re.IGNORECASE)
    name = _MONTH_PATTERN.sub("", name)

    # Replace underscores with spaces and clean up
    name = name.replace("_", " ").strip()

    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)

    # Normalise capitalisation for known skills
    return canonical_skill_name(name)


def extract_period(filename: str) -> tuple[str, int, int] | None:
    """Extract the period from a filename.

    Returns (label, month_number, year) or None.

    Example::

        'PM Consultas_may26.csv' \u2192 ('Mayo 2026', 5, 2026)
    """
    match = _MONTH_PATTERN.search(filename.replace(".csv", ""))
    if not match:
        return None

    month_word = match.group(1).lower()
    digits = match.group(2)

    month_name, month_num = _MONTH_MAP.get(month_word, ("?", 0))
    year = int(digits)
    if year < 100:
        year += 2000

    return f"{month_name} {year}", month_num, year


def find_campaign(skill_name: str) -> str:
    """Find which campaign a skill belongs to.

    Returns the campaign name or 'Sin asignar' if not found.
    """
    normalized = skill_name.lower().strip()
    return _SKILL_TO_CAMPAIGN.get(normalized, "Sin asignar")


def classify_files(filenames: list[str]) -> dict[str, list[dict]]:
    """Classify a list of filenames into campaigns.

    Returns a dict keyed by campaign name, with lists of
    ``{"filename": ..., "skill": ...}`` dicts.

    Example::

        {
            "Turnos": [
                {"filename": "Turnos Estudios_jun26.csv", "skill": "Turnos Estudios"},
                {"filename": "Gipfel Cober_jun26.csv", "skill": "Gipfel Cober"},
            ],
            "Conmutador": [
                {"filename": "Conmutador_jun26.csv", "skill": "Conmutador"},
            ],
            ...
        }
    """
    result: dict[str, list[dict]] = {}

    for fn in filenames:
        skill = extract_skill_name(fn)
        campaign = find_campaign(skill)
        entry = {"filename": fn, "skill": skill}

        if campaign not in result:
            result[campaign] = []
        result[campaign].append(entry)

    return result


def is_gipfel_skill(skill_name: str) -> bool:
    """Check if a skill is a Gipfel skill."""
    return skill_name.lower().strip() in GIPFEL_SKILLS
