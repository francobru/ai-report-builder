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
_MONTH_PATTERN = re.compile(
    r"[_ ]+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\d{2}$",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "ene": ("Enero", 1),   "feb": ("Febrero", 2),  "mar": ("Marzo", 3),
    "abr": ("Abril", 4),   "may": ("Mayo", 5),      "jun": ("Junio", 6),
    "jul": ("Julio", 7),   "ago": ("Agosto", 8),    "sep": ("Septiembre", 9),
    "oct": ("Octubre", 10), "nov": ("Noviembre", 11), "dic": ("Diciembre", 12),
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
        "0800 onco",
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
        "0800 coca cola",
    ],
    "Portal": [
        "Portal Digital",
        "Portal Paciente",
    ],
    "Agendas": [
        "Agendas medicas",
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

    # Remove month-year suffix
    name = _MONTH_PATTERN.sub("", name)

    # Replace underscores with spaces and clean up
    name = name.replace("_", " ").strip()

    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)

    return name


def extract_period(filename: str) -> tuple[str, int, int] | None:
    """Extract the period from a filename.

    Returns (label, month_number, year) or None.

    Example::

        'PM Consultas_may26.csv' \u2192 ('Mayo 2026', 5, 2026)
    """
    match = _MONTH_PATTERN.search(filename.replace(".csv", ""))
    if not match:
        return None

    month_abbr = match.group(1).lower()
    year_suffix = match.group(0)[-2:]

    month_name, month_num = _MONTH_MAP.get(month_abbr, ("?", 0))
    year = 2000 + int(year_suffix)

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
