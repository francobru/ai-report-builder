"""Data validation against a plugin's schema.

Validates:
- Required columns exist
- No completely empty required columns
- Date column is parseable
- Numeric columns have valid ranges
- Detects and reports anomalies (e.g. negative call counts)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.plugin_registry import DataSchema


@dataclass
class ValidationResult:
    """Outcome of validating a DataFrame against a schema."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_count: int = 0
    date_range: str = ""

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def summary(self) -> str:
        parts = [f"{self.row_count} filas"]
        if self.date_range:
            parts.append(f"per\u00edodo {self.date_range}")
        if self.errors:
            parts.append(f"{len(self.errors)} errores")
        if self.warnings:
            parts.append(f"{len(self.warnings)} advertencias")
        return " \u00b7 ".join(parts)


def validate(
    df: pd.DataFrame,
    schema: DataSchema,
    source_name: str = "",
) -> ValidationResult:
    """Validate *df* against *schema* and return a :class:`ValidationResult`.

    Parameters
    ----------
    df:
        The DataFrame to validate.
    schema:
        Expected schema from the plugin.
    source_name:
        Label used in error messages (e.g. the filename).
    """
    result = ValidationResult(row_count=len(df))
    prefix = f"[{source_name}] " if source_name else ""

    # -- Check required columns -------------------------------------------
    df_cols = set(df.columns)
    for col_spec in schema.columns:
        if col_spec.required and col_spec.name not in df_cols:
            result.add_error(
                f"{prefix}Columna requerida '{col_spec.name}' no encontrada. "
                f"Columnas disponibles: {sorted(df_cols)}"
            )

    if not result.is_valid:
        return result  # no point continuing if columns are missing

    # -- Check for empty required columns ---------------------------------
    for col_spec in schema.columns:
        if col_spec.required and col_spec.name in df_cols:
            if df[col_spec.name].isna().all():
                result.add_error(
                    f"{prefix}Columna '{col_spec.name}' est\u00e1 completamente vac\u00eda."
                )
            elif df[col_spec.name].isna().any():
                n_missing = int(df[col_spec.name].isna().sum())
                result.add_warning(
                    f"{prefix}Columna '{col_spec.name}' tiene {n_missing} valor(es) faltante(s)."
                )

    # -- Check date parsing -----------------------------------------------
    if "date" in df.columns:
        n_bad = int(df["date"].isna().sum())
        if n_bad == len(df):
            result.add_error(f"{prefix}No se pudo parsear ninguna fecha.")
        elif n_bad > 0:
            result.add_warning(f"{prefix}{n_bad} fecha(s) no parseada(s).")

        valid_dates = df["date"].dropna()
        if not valid_dates.empty:
            d_min = valid_dates.min().strftime("%d/%m/%Y")
            d_max = valid_dates.max().strftime("%d/%m/%Y")
            result.date_range = f"{d_min} \u2013 {d_max}"

    # -- Sanity checks on numeric columns ---------------------------------
    numeric_checks = {
        "TOTALCALLS": ("Recibidas", 0, None),
        "TRANSFER": ("Atendidas", 0, None),
        "PCTATT": ("Nivel de Atenci\u00f3n", 0, 100),
    }
    for col, (label, vmin, vmax) in numeric_checks.items():
        if col not in df_cols:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if vmin is not None and (series < vmin).any():
            result.add_warning(f"{prefix}'{label}' contiene valores negativos.")
        if vmax is not None and (series > vmax).any():
            result.add_warning(f"{prefix}'{label}' contiene valores > {vmax}.")

    # -- Check row count --------------------------------------------------
    if len(df) == 0:
        result.add_error(f"{prefix}El archivo no contiene datos (0 filas).")

    return result
