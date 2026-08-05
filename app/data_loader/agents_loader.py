"""Agent productivity loader for the Plan Medico report.

Reads the monthly agents spreadsheet, whose columns are:
    OPERADOR, Fecha, Modalidad OK, Tiempo de Sesion, Tiempo no disponible,
    Hora de Logueo, Utilizacion%, OCUPACION, Atendidas, Salientes,
    AHT, ASA, Cierres

Durations arrive as pandas Timedelta and are converted to the
"123h 12m" format used in the report.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


COLUMN_ALIASES = {
    "operador": "operador",
    "tiempo de sesion": "logueo",
    "tiempo de sesi\u00f3n": "logueo",
    "tiempo no disponible": "no_disponible",
    "utilizacion%": "utilizacion",
    "utilizaci\u00f3n%": "utilizacion",
    "ocupacion": "ocupacion",
    "ocupaci\u00f3n": "ocupacion",
    "atendidas": "atendidas",
    "salientes": "salientes",
    "aht": "aht",
    "asa": "asa",
    "cierres": "cierres",
}


def _to_timedelta(value) -> pd.Timedelta | None:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timedelta):
        return value
    try:
        return pd.to_timedelta(str(value))
    except Exception:
        return None


def format_hm(td) -> str:
    """Format a duration as '123h 12m'."""
    td = _to_timedelta(td)
    if td is None:
        return "-"
    total_min = int(td.total_seconds() // 60)
    return f"{total_min // 60}h {total_min % 60:02d}m"


def format_ms(td) -> str:
    """Format a short duration as 'MM:SS' (used for AHT/ASA)."""
    td = _to_timedelta(td)
    if td is None:
        return "-"
    secs = int(round(td.total_seconds()))
    return f"{secs // 60:02d}:{secs % 60:02d}"


def load_agents_xlsx(filepath: Path, sheet_name=0) -> pd.DataFrame:
    """Load and normalise the agents spreadsheet."""
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    rename = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in COLUMN_ALIASES:
            rename[col] = COLUMN_ALIASES[key]
    df = df.rename(columns=rename)

    for col in ("logueo", "no_disponible", "aht", "asa"):
        if col in df.columns:
            df[col] = df[col].apply(_to_timedelta)

    for col in ("atendidas", "salientes", "cierres", "utilizacion", "ocupacion"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "operador" in df.columns:
        df["operador"] = df["operador"].astype(str).str.strip()
        df = df[df["operador"].str.len() > 0]

    return df.reset_index(drop=True)


def validate_agents(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Check the columns the report needs are present."""
    needed = ["operador", "logueo", "no_disponible", "atendidas", "cierres"]
    missing = [c for c in needed if c not in df.columns]
    errors = []
    if missing:
        errors.append("Faltan columnas: " + ", ".join(missing))
    if len(df) == 0:
        errors.append("El archivo no contiene operadores.")
    return (not errors), errors


def agents_summary(df: pd.DataFrame) -> dict:
    """Aggregate totals for the header cards of the agents section."""
    logueo = df["logueo"].dropna().sum() if "logueo" in df.columns else pd.Timedelta(0)
    nodisp = df["no_disponible"].dropna().sum() if "no_disponible" in df.columns else pd.Timedelta(0)
    pct_nodisp = (nodisp.total_seconds() / logueo.total_seconds() * 100
                  if getattr(logueo, "total_seconds", lambda: 0)() else 0.0)

    # Weighted average handle time, using each agent's answered calls
    aht_str = "-"
    if "aht" in df.columns and "atendidas" in df.columns:
        secs, calls = 0.0, 0.0
        for _, r in df.iterrows():
            td = _to_timedelta(r.get("aht"))
            n = float(r.get("atendidas") or 0)
            if td is not None and n > 0:
                secs += td.total_seconds() * n
                calls += n
        if calls:
            avg = int(round(secs / calls))
            aht_str = f"{avg // 60:02d}:{avg % 60:02d}"

    return {
        "operadores": int(len(df)),
        "logueo": format_hm(logueo),
        "no_disponible": format_hm(nodisp),
        "pct_no_disponible": round(pct_nodisp, 1),
        "atendidas": int(df["atendidas"].sum()) if "atendidas" in df.columns else 0,
        "cierres": int(df["cierres"].sum()) if "cierres" in df.columns else 0,
        "aht": aht_str,
    }


def agents_table(df: pd.DataFrame) -> list[dict]:
    """Build the per-operator rows, sorted by logged time (desc)."""
    rows = []
    for _, r in df.iterrows():
        log_td = _to_timedelta(r.get("logueo"))
        nd_td = _to_timedelta(r.get("no_disponible"))
        pct_nd = (nd_td.total_seconds() / log_td.total_seconds() * 100
                  if log_td and nd_td and log_td.total_seconds() else 0.0)

        util = float(r.get("utilizacion") or 0)
        ocup = float(r.get("ocupacion") or 0)
        if util <= 1:      # stored as a fraction
            util *= 100
        if ocup <= 1:
            ocup *= 100

        rows.append({
            "operador": str(r.get("operador", "")),
            "logueo": format_hm(log_td),
            "no_disponible": format_hm(nd_td),
            "pct_no_disponible": f"{pct_nd:.1f}%".replace(".", ","),
            "atendidas": f"{int(r.get('atendidas') or 0):,}".replace(",", "."),
            "cierres": f"{int(r.get('cierres') or 0):,}".replace(",", "."),
            "utilizacion": f"{util:.1f}%".replace(".", ","),
            "ocupacion": f"{ocup:.1f}%".replace(".", ","),
            "_sort": log_td.total_seconds() if log_td else 0,
        })
    rows.sort(key=lambda x: -x["_sort"])
    for r in rows:
        r.pop("_sort", None)
    return rows
