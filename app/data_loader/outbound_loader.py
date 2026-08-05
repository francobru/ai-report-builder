"""Outbound calls (llamadas salientes) loader and aggregator.

The outbound CSV has ONE ROW PER CALL with columns:
    logdate, logtime, agentid, phone, lengthcall, sdate, stime, sresult, result

Where:
    - sresult: text result ("Conectado", "Cancelada por Asesor", "Ocupado", etc.)
    - result: numeric code
    - sdate: date string DD/MM/YYYY
    - logdate: date int YYYYMMDD

This module aggregates the raw calls into:
    - Total count
    - Distribution by result (sresult)
    - Daily distribution (by date)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_outbound_csv(filepath: Path, separator: str = None) -> pd.DataFrame:
    """Load an outbound calls CSV (one row per call).

    Auto-detects separator (tab or semicolon or comma).
    """
    # Try to detect the separator by reading the first line
    with open(filepath, encoding="utf-8", errors="replace") as fh:
        first_line = fh.readline()

    if separator is None:
        if "\t" in first_line:
            separator = "\t"
        elif ";" in first_line:
            separator = ";"
        else:
            separator = ","

    df = pd.read_csv(filepath, sep=separator, engine="python", dtype=str)
    df.columns = df.columns.str.strip().str.lower()

    # Parse date from sdate (DD/MM/YYYY) or logdate (YYYYMMDD)
    if "sdate" in df.columns:
        df["date"] = pd.to_datetime(df["sdate"], format="%d/%m/%Y", errors="coerce")
    if ("date" not in df.columns or df["date"].isna().all()) and "logdate" in df.columns:
        df["date"] = pd.to_datetime(df["logdate"], format="%Y%m%d", errors="coerce")

    return df


def aggregate_outbound(df: pd.DataFrame) -> dict:
    """Aggregate outbound calls into report-ready structures.

    Returns a dict with:
        - total: int
        - by_result: dict {result_name: count} sorted descending
        - daily: DataFrame with columns [date, count]
    """
    result = {
        "total": len(df),
        "by_result": {},
        "daily": pd.DataFrame(),
    }

    # Distribution by result
    if "sresult" in df.columns:
        counts = df["sresult"].str.strip().value_counts()
        result["by_result"] = counts.to_dict()

    # Daily distribution
    if "date" in df.columns:
        daily = df.dropna(subset=["date"]).groupby("date").size().reset_index(name="count")
        daily = daily.sort_values("date")
        result["daily"] = daily

    return result


def count_rotaciones_am(df: pd.DataFrame) -> int:
    """Count 'Rotaciones AM' \u2014 calls that resulted in a rotation to medical agendas.

    NOTE: In the original May report this figure comes from a separate
    supervisor-completed cancellation registry, not from this CSV.
    Here we approximate it as calls with result 'Conectado' if no better
    signal exists.  This can be refined once the exact rule is known.
    """
    if "sresult" not in df.columns:
        return 0
    # Placeholder: count connected calls (to be refined with business rule)
    return int((df["sresult"].str.strip() == "Conectado").sum())
