"""Historical monthly totals for the monthly-trend analysis.

Stores per-month totals (recibidas, atendidas, nivel de atenci\u00f3n) so the
report can show the year-to-date trend (page 12 of the original report).

The data from the May 2026 report is pre-loaded here. As new reports are
generated, their totals are appended (persisted to a JSON file).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


# Persistent storage location
_HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "monthly_history.json"


@dataclass
class MonthlyRecord:
    """Totals for one month."""
    year: int
    month: int          # 1-12
    month_name: str     # "Enero", etc.
    recibidas: int
    atendidas: int
    nivel_atencion: float  # percentage

    @property
    def key(self) -> str:
        return f"{self.year}-{self.month:02d}"


# Pre-loaded data from the May 2026 report (page 12)
_SEED_DATA = [
    MonthlyRecord(2026, 1, "Enero",   79134, 73033, 92.3),
    MonthlyRecord(2026, 2, "Febrero", 77037, 67275, 87.3),
    MonthlyRecord(2026, 3, "Marzo",   87251, 80068, 91.8),
    MonthlyRecord(2026, 4, "Abril",   83699, 73880, 88.3),
    MonthlyRecord(2026, 5, "Mayo",    77530, 69740, 90.0),
]

_MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _load_history() -> dict[str, MonthlyRecord]:
    """Load history from disk, seeding with report data if empty."""
    records: dict[str, MonthlyRecord] = {}

    # Start with seed data
    for rec in _SEED_DATA:
        records[rec.key] = rec

    # Overlay any persisted data
    if _HISTORY_FILE.exists():
        try:
            with open(_HISTORY_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            for item in data:
                rec = MonthlyRecord(**item)
                records[rec.key] = rec
        except Exception:
            pass

    return records


def _save_history(records: dict[str, MonthlyRecord]) -> None:
    """Persist history to disk."""
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(rec) for rec in records.values()]
    with open(_HISTORY_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def add_month(year: int, month: int, recibidas: int, atendidas: int,
              nivel_atencion: float) -> None:
    """Add or update a month's totals and persist.

    Called automatically each time a report is generated, so the
    trend accumulates over time.
    """
    records = _load_history()
    rec = MonthlyRecord(
        year=year, month=month, month_name=_MONTH_NAMES.get(month, "?"),
        recibidas=int(recibidas), atendidas=int(atendidas),
        nivel_atencion=round(float(nivel_atencion), 1),
    )
    records[rec.key] = rec
    _save_history(records)


def get_trend(year: int, up_to_month: int) -> list[MonthlyRecord]:
    """Return the ordered list of monthly records for *year* up to *up_to_month*.

    Example: get_trend(2026, 5) \u2192 [Enero, Febrero, Marzo, Abril, Mayo]
    """
    records = _load_history()
    result = [
        rec for rec in records.values()
        if rec.year == year and rec.month <= up_to_month
    ]
    result.sort(key=lambda r: r.month)
    return result

# ======================================================================
# CSV import / export
# ======================================================================
# Streamlit Cloud wipes the container's disk on every restart, so the JSON
# above cannot be relied on between months. The team keeps a small CSV in a
# shared folder instead: they upload it with the monthly files and download
# the updated one afterwards. It is a plain semicolon CSV so it opens in
# Excel and can be corrected by hand if a month was ever generated wrong.

CSV_HEADER = "Anio;Mes;Recibidas;Atendidas;Nivel de Atencion"

_NAME_TO_MONTH = {}
for _num, _name in _MONTH_NAMES.items():
    _NAME_TO_MONTH[_name.lower()] = _num
    _NAME_TO_MONTH[_name[:3].lower()] = _num
_NAME_TO_MONTH["setiembre"] = 9


def _fmt_na(value: float) -> str:
    return f"{float(value):.1f}".replace(".", ",")


def export_history_csv(year: int | None = None) -> str:
    """Return the whole history as CSV text, ready to download.

    Rows are ordered by year and month. When *year* is given, only that
    year is exported.
    """
    records = sorted(_load_history().values(), key=lambda r: (r.year, r.month))
    if year is not None:
        records = [r for r in records if r.year == year]
    lines = [CSV_HEADER]
    for r in records:
        lines.append(f"{r.year};{r.month_name};{r.recibidas};"
                     f"{r.atendidas};{_fmt_na(r.nivel_atencion)}")
    return "\r\n".join(lines) + "\r\n"


def _parse_number(text: str) -> float | None:
    """Read a number written the Argentine way ('79.134' or '92,3')."""
    txt = str(text).strip().replace(" ", "")
    if not txt:
        return None
    if "," in txt:                     # comma is the decimal mark
        txt = txt.replace(".", "").replace(",", ".")
    elif txt.count(".") >= 1 and len(txt.split(".")[-1]) == 3:
        txt = txt.replace(".", "")     # dot used as thousands separator
    try:
        return float(txt)
    except ValueError:
        return None


def import_history_csv(text: str) -> tuple[int, list[str]]:
    """Load a history CSV into the store.

    Returns (rows imported, warnings). Rows that cannot be read are
    reported instead of silently dropped.
    """
    warnings: list[str] = []
    records = _load_history()
    imported = 0

    if text.startswith("\ufeff"):
        text = text[1:]

    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 5:
            parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            warnings.append(f"Linea {i}: se esperaban 5 columnas.")
            continue
        if parts[0].lower().startswith("anio") or parts[0].lower().startswith("ano"):
            continue                                    # header

        year_v = _parse_number(parts[0])
        month = _NAME_TO_MONTH.get(parts[1].lower())
        rec = _parse_number(parts[2])
        att = _parse_number(parts[3])
        na = _parse_number(parts[4])

        if year_v is None or month is None or rec is None or att is None:
            warnings.append(f"Linea {i}: no pude leer '{line[:40]}'.")
            continue
        if na is None:
            na = (att / rec * 100) if rec else 0.0

        rec_obj = MonthlyRecord(
            year=int(year_v), month=month, month_name=_MONTH_NAMES[month],
            recibidas=int(rec), atendidas=int(att), nivel_atencion=round(na, 1),
        )
        records[rec_obj.key] = rec_obj
        imported += 1

    if imported:
        _save_history(records)
    return imported, warnings


def missing_months(year: int, up_to_month: int) -> list[str]:
    """Names of the months with no data yet, up to *up_to_month*."""
    present = {r.month for r in get_trend(year, up_to_month)}
    return [_MONTH_NAMES[m] for m in range(1, up_to_month + 1) if m not in present]
