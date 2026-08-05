"""CSV loader for Tecnovoz-format files.

Handles the specific quirks of the Tecnovoz export:
- Semicolon separator
- Comma as decimal separator
- Date in DD/MM/YYYY format (NUMDAY) and YYYYMMDD (LOGDATE)
- Summary "Total" row at the bottom
- Time columns in HH:MM:SS format
- Windows line endings (\\r\\n)
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from app.core.plugin_registry import DataSchema


# Columns that contain time values (HH:MM:SS) \u2014 never parse as numeric
_TIME_COLUMNS = {"AVGCONNWAIT", "AVGABNWAIT", "AVGTALKTIME"}


def load_csv(
    filepath: Path,
    schema: DataSchema | None = None,
) -> pd.DataFrame:
    """Read a single Tecnovoz CSV and return a cleaned DataFrame.

    Parameters
    ----------
    filepath:
        Path to the ``.csv`` file.
    schema:
        Optional schema for separator/decimal/encoding overrides.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame **without** the summary "Total" row.
        Numeric columns are cast to float; date column is parsed.
    """
    sep = schema.separator if schema else ";"
    decimal = schema.decimal if schema else ","
    encoding = schema.encoding if schema else "utf-8"

    # Some Tecnovoz exports arrive with NUL bytes where the decimal separator
    # should be ("79\x0064" instead of "79,64"), which would leave the affected
    # columns unusable. Sanitise the raw text before parsing.
    raw = filepath.read_bytes()
    if b"\x00" in raw:
        raw = raw.replace(b"\x00", decimal.encode(encoding, errors="ignore"))
        text = raw.decode(encoding, errors="replace")
        df = pd.read_csv(io.StringIO(text), sep=sep, decimal=decimal, engine="python")
    else:
        df = pd.read_csv(
            filepath,
            sep=sep,
            decimal=decimal,
            encoding=encoding,
            engine="python",
        )

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    # Remove trailing empty columns (Tecnovoz sometimes adds a trailing ";")
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

    # Remove the summary Total row if present
    if schema and schema.has_total_row:
        df = _remove_total_row(df)

    # Parse dates
    df = _parse_dates(df, schema)

    # Convert numeric-looking columns (skip time columns)
    df = _coerce_numerics(df)

    # Store source filename for traceability
    df.attrs["source_file"] = filepath.name

    return df


def load_multiple_csvs(
    filepaths: list[Path],
    schema: DataSchema | None = None,
) -> dict[str, pd.DataFrame]:
    """Load several CSVs and return a dict keyed by filename (stem).

    Example return::

        {
            "PM_Consultas_may26": <DataFrame>,
            "Conmutador_may26":   <DataFrame>,
        }
    """
    result: dict[str, pd.DataFrame] = {}
    for fp in filepaths:
        df = load_csv(fp, schema=schema)
        result[fp.stem] = df
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _remove_total_row(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the row whose first column value starts with 'Total' (case-insensitive)."""
    first_col = df.columns[0]
    mask = df[first_col].astype(str).str.strip().str.lower().str.startswith("total")
    return df[~mask].reset_index(drop=True)


def _parse_dates(df: pd.DataFrame, schema: DataSchema | None) -> pd.DataFrame:
    """Attempt to parse date columns into datetime."""
    date_col = schema.date_column if schema else "LOGDATE"

    # LOGDATE is YYYYMMDD integer
    if "LOGDATE" in df.columns:
        df["LOGDATE"] = pd.to_numeric(df["LOGDATE"], errors="coerce")
        df["date"] = pd.to_datetime(df["LOGDATE"], format="%Y%m%d", errors="coerce")

    # NUMDAY is DD/MM/YYYY string
    if "NUMDAY" in df.columns:
        df["date_numday"] = pd.to_datetime(
            df["NUMDAY"], format="%d/%m/%Y", errors="coerce"
        )
        # Use NUMDAY as canonical date if LOGDATE parsing failed
        if "date" not in df.columns or df["date"].isna().all():
            df["date"] = df["date_numday"]

    return df


def _coerce_numerics(df: pd.DataFrame) -> pd.DataFrame:
    """Convert columns that look numeric to float, skipping time columns."""
    for col in df.columns:
        if col in _TIME_COLUMNS or col.startswith("date") or col in ("NUMDAY", "LOGDATE"):
            continue
        if df[col].dtype == object:
            # Try converting comma-decimal strings like "81,70" \u2192 81.70
            try:
                converted = df[col].astype(str).str.replace(",", ".").astype(float)
                df[col] = converted
            except (ValueError, TypeError):
                pass
    return df
