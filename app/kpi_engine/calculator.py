"""KPI calculation engine.

Given a DataFrame and a list of :class:`KPIDefinition` objects, computes
every KPI and returns a dict of results.

Supports aggregation types: sum, mean, custom, mean_time.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from app.core.plugin_registry import KPIDefinition


def compute_kpis(
    df: pd.DataFrame,
    kpi_defs: list[KPIDefinition],
) -> dict[str, dict]:
    """Compute all KPIs for the given DataFrame.

    Returns a dict like::

        {
            "recibidas": {
                "value": 8646.0,
                "formatted": "8.646",
                "label": "Recibidas",
                "unit": "",
            },
            ...
        }
    """
    results: dict[str, dict] = {}

    for kpi in kpi_defs:
        value = _compute_single(df, kpi)
        formatted = _format_value(value, kpi)
        results[kpi.id] = {
            "value": value,
            "formatted": formatted,
            "label": kpi.label,
            "unit": kpi.unit,
            "format_str": kpi.format_str,
        }

    return results


def compute_variation(
    current: dict[str, dict],
    previous: dict[str, dict],
) -> dict[str, dict]:
    """Compute percentage variations between current and previous KPIs.

    Returns a dict like::

        {
            "recibidas": {
                "variation_pct": -7.37,
                "direction": "down",
                "formatted": "▼ 7,37%",
            },
            ...
        }
    """
    variations: dict[str, dict] = {}

    for kpi_id, cur in current.items():
        if kpi_id not in previous:
            continue
        prev_val = previous[kpi_id]["value"]
        cur_val = cur["value"]

        if prev_val is None or cur_val is None:
            continue

        # Skip non-numeric values (time KPIs return strings like "00:03:40")
        if not isinstance(cur_val, (int, float)) or not isinstance(prev_val, (int, float)):
            continue

        if prev_val == 0:
            variations[kpi_id] = {
                "variation_pct": None,
                "direction": "neutral",
                "formatted": "—",
            }
            continue

        # Nivel de Atención uses percentage-POINT difference (e.g. 90,0 - 88,3 = 1,7 p.p.)
        # Volume KPIs (recibidas, atendidas, promedios) use relative percentage change.
        if kpi_id == "nivel_atencion":
            diff = cur_val - prev_val
            direction = "up" if diff > 0 else "down" if diff < 0 else "neutral"
            arrow = "▲" if direction == "up" else "▼" if direction == "down" else "—"
            formatted = f"{arrow} {abs(diff):.2f}".replace(".", ",") + " p.p."
            variations[kpi_id] = {
                "variation_pct": round(diff, 2),
                "direction": direction,
                "formatted": formatted,
            }
            continue

        pct = ((cur_val - prev_val) / abs(prev_val)) * 100
        direction = "up" if pct > 0 else "down" if pct < 0 else "neutral"
        arrow = "▲" if direction == "up" else "▼" if direction == "down" else "—"
        formatted = f"{arrow} {abs(pct):.2f}%".replace(".", ",")

        variations[kpi_id] = {
            "variation_pct": round(pct, 2),
            "direction": direction,
            "formatted": formatted,
        }

    return variations


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _compute_single(df: pd.DataFrame, kpi: KPIDefinition) -> object:
    """Compute a single KPI value."""

    if kpi.aggregation == "sum":
        return float(df[kpi.source_column].sum())

    if kpi.aggregation == "mean":
        return _compute_daily_average(df, kpi.source_column)

    if kpi.aggregation == "custom":
        return _compute_custom(df, kpi)

    if kpi.aggregation == "mean_time":
        return _compute_mean_time(df, kpi.source_column)

    raise ValueError(f"Unknown aggregation type: {kpi.aggregation}")


def _compute_daily_average(df: pd.DataFrame, column: str) -> float:
    """Compute daily average = total / number of distinct days with activity.

    "Days with activity" = distinct dates where at least one call was received
    (TOTALCALLS > 0).  This gives the correct average even when multiple skills
    with different operating days are combined.

    Example: Conmutador operates 31 days in July → total / 31.
              Plan Médico operates 20 weekdays → total / 20.
    """
    if "date" not in df.columns or "TOTALCALLS" not in df.columns:
        # Fallback to simple mean if no date column
        return float(df[column].mean())

    # Group by date and sum received calls; count days with activity
    daily_totals = df.groupby("date")["TOTALCALLS"].sum()
    active_days = int((daily_totals > 0).sum())

    if active_days == 0:
        return 0.0

    total = float(df[column].sum())
    return total / active_days


def _compute_custom(df: pd.DataFrame, kpi: KPIDefinition) -> float | None:
    """Handle custom KPIs that need special logic."""
    if kpi.id == "nivel_atencion":
        total = df["TOTALCALLS"].sum()
        attended = df["TRANSFER"].sum()
        if total == 0:
            return 0.0
        return round((attended / total) * 100, 2)

    raise ValueError(f"No custom logic defined for KPI: {kpi.id}")


def _compute_mean_time(df: pd.DataFrame, column: str) -> str:
    """Compute weighted-average time from HH:MM:SS strings.

    Since each row represents a day with different call volumes,
    a simple mean of times is acceptable here (Tecnovoz already
    provides the daily average).
    """
    times = df[column].dropna().astype(str)
    if times.empty:
        return "00:00:00"

    total_seconds = 0.0
    count = 0
    for t in times:
        secs = _time_str_to_seconds(t)
        if secs is not None:
            total_seconds += secs
            count += 1

    if count == 0:
        return "00:00:00"

    avg_seconds = total_seconds / count
    return _seconds_to_time_str(avg_seconds)


def _time_str_to_seconds(time_str: str) -> float | None:
    """Convert 'HH:MM:SS' to total seconds."""
    parts = time_str.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h * 3600 + m * 60 + s
    except ValueError:
        return None


def _seconds_to_time_str(seconds: float) -> str:
    """Convert total seconds to 'HH:MM:SS'."""
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _format_value(value: object, kpi: KPIDefinition) -> str:
    """Format a KPI value for display."""
    if value is None:
        return "—"

    if isinstance(value, str):
        return value

    try:
        formatted = kpi.format_str.format(value)
        # Use Argentine locale: dot for thousands, comma for decimals
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except (ValueError, TypeError):
        return str(value)
