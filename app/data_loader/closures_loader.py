"""Closure (tipificaciones) loader for the Plan Medico report.

The source is one CSV per day with the columns:
    USER_NAME; SKILL_DESC; CODE_DESC; CODE_COUNT; USERID; CODEID

Several daily files are added together to build the monthly picture.
"""

from __future__ import annotations

import calendar
import datetime
import io
import re
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["USER_NAME", "SKILL_DESC", "CODE_DESC", "CODE_COUNT"]

# ======================================================================
# Date taken from the file name
# ======================================================================

# Matches the date in names like "cierres_22-07-26", "cierres 22/07/2026",
# "cierres_22.07.26" or "Cierres-1-8-2026".
_DATE_PATTERN = re.compile(r"(\d{1,4})[-_./](\d{1,2})[-_./](\d{2,4})")


def date_from_filename(filename: str):
    """Return the date encoded in a closures file name, or None.

    Day-first is assumed (Argentine convention), e.g. "22-07-26" is the
    22nd of July 2026. A leading 4-digit number is read as a year instead.
    """
    stem = str(filename).strip()
    for ext in (".csv", ".CSV", ".txt", ".TXT"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    m = _DATE_PATTERN.search(stem)
    if not m:
        return None

    a, b, c = m.group(1), m.group(2), m.group(3)
    try:
        if len(a) == 4:                       # YYYY-MM-DD
            year, month, day = int(a), int(b), int(c)
        else:                                 # DD-MM-YY(YY)
            day, month, year = int(a), int(b), int(c)
            if year < 100:
                year += 2000
        return datetime.date(year, month, day)
    except ValueError:
        return None


def describe_coverage(dates: list) -> dict:
    """Summarise which days a set of closure files covers.

    Returns: period label, sorted days, duplicates and missing weekdays.
    """
    valid = sorted(d for d in dates if d is not None)
    info = {"period": "", "days": valid, "duplicates": [],
            "missing_weekdays": [], "unknown": sum(1 for d in dates if d is None)}
    if not valid:
        return info

    seen, dupes = set(), []
    for d in valid:
        if d in seen:
            dupes.append(d)
        seen.add(d)
    info["duplicates"] = sorted(set(dupes))

    months = {(d.year, d.month) for d in valid}
    names = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo",
             6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre",
             10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
    if len(months) == 1:
        y, m = next(iter(months))
        info["period"] = f"{names[m]} {y}"

        # Business days of that month with no file
        import calendar
        last = calendar.monthrange(y, m)[1]
        present = {d.day for d in valid}
        info["missing_weekdays"] = [
            day for day in range(1, last + 1)
            if datetime.date(y, m, day).weekday() < 5 and day not in present
        ]
    else:
        info["period"] = "Varios meses"
    return info



def load_closures_csv(filepath: Path, separator: str = ";",
                      encoding: str = "utf-8") -> pd.DataFrame:
    """Load one daily closures CSV."""
    raw = filepath.read_bytes()
    if b"\x00" in raw:
        raw = raw.replace(b"\x00", b",")
    text = raw.decode(encoding, errors="replace")

    df = pd.read_csv(io.StringIO(text), sep=separator, engine="python")
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

    for col in ("USER_NAME", "SKILL_DESC", "CODE_DESC"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    if "CODE_COUNT" in df.columns:
        df["CODE_COUNT"] = pd.to_numeric(df["CODE_COUNT"], errors="coerce").fillna(0)

    return df


def load_and_merge_closures(filepaths: list[Path],
                            names: list[str] | None = None) -> pd.DataFrame:
    """Load several daily files and add them into a single monthly frame.

    *names* lets the caller pass the ORIGINAL file names (an upload is saved
    to a temporary file, so its name is lost); the date of each day is read
    from there and kept in a ``fecha`` column.
    """
    frames = []
    for i, fp in enumerate(filepaths):
        try:
            df = load_closures_csv(Path(fp))
            label = names[i] if names and i < len(names) else Path(fp).name
            df["fecha"] = date_from_filename(label)
            df["_archivo"] = label
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def validate_closures(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Check the expected columns are present."""
    errors = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append("Faltan columnas: " + ", ".join(missing))
    if len(df) == 0:
        errors.append("El archivo no contiene datos.")
    return (not errors), errors


def closures_for_skill(df: pd.DataFrame, skill: str) -> pd.DataFrame:
    """Filter the rows belonging to one skill (case/spacing insensitive)."""
    if "SKILL_DESC" not in df.columns:
        return df.iloc[0:0]
    key = skill.upper().replace(" ", "")
    mask = df["SKILL_DESC"].str.upper().str.replace(" ", "", regex=False) == key
    return df[mask]


def top_reasons(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Return the top closure reasons with their share of the total.

    Columns: CODE_DESC, cierres, pct
    """
    if len(df) == 0 or "CODE_DESC" not in df.columns:
        return pd.DataFrame(columns=["CODE_DESC", "cierres", "pct"])

    grouped = (df.groupby("CODE_DESC")["CODE_COUNT"].sum()
                 .sort_values(ascending=False).reset_index())
    grouped = grouped.rename(columns={"CODE_COUNT": "cierres"})
    total = grouped["cierres"].sum()
    grouped["pct"] = (grouped["cierres"] / total * 100).round(1) if total else 0.0
    return grouped.head(top_n)


def total_closures(df: pd.DataFrame) -> int:
    """Total number of closures in the frame."""
    if len(df) == 0 or "CODE_COUNT" not in df.columns:
        return 0
    return int(df["CODE_COUNT"].sum())
