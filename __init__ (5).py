"""Historical monthly totals for the monthly-trend analysis.

Stores per-month totals (recibidas, atendidas, nivel de atención) so the
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

    Example: get_trend(2026, 5) → [Enero, Febrero, Marzo, Abril, Mayo]
    """
    records = _load_history()
    result = [
        rec for rec in records.values()
        if rec.year == year and rec.month <= up_to_month
    ]
    result.sort(key=lambda r: r.month)
    return result
