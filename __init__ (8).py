"""Natural-language question answering over the report data.

Answers questions like:
    "cuántas llamadas atendidas el 15 de junio en Turnos PM Estudios"
    "nivel de atención de Conmutador"
    "total recibidas el 4 de mayo"
    "cuál fue el peor día de Plan Médico"

No AI API is used: the domain is narrow (known skills, known metrics,
dates within the period), so the question is parsed with rules and the
answer is read directly from the data. That makes it free, instant and
impossible to hallucinate.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd


# ======================================================================
# Metric definitions
# ======================================================================

METRICS = {
    "atendidas": {
        "column": "TRANSFER", "kind": "sum", "label": "llamadas atendidas",
        "keywords": ["atendida", "atendido", "contestada", "transfer"],
    },
    "recibidas": {
        "column": "TOTALCALLS", "kind": "sum", "label": "llamadas recibidas",
        "keywords": ["recibida", "recibido", "entrante", "total de llamada",
                     "totalcalls", "ingresaron", "llegaron"],
    },
    "no_atendidas": {
        "column": "NOTRANSFER", "kind": "sum", "label": "llamadas no atendidas",
        "keywords": ["no atendida", "perdida", "abandonada", "notransfer",
                     "sin atender"],
    },
    "nivel_atencion": {
        "column": None, "kind": "na", "label": "nivel de atención",
        "keywords": ["nivel de atencion", "nivel atencion", " na ", "porcentaje de atencion",
                     "% de atencion", "tasa de atencion"],
    },
    "conversacion": {
        "column": "AVGTALKTIME", "kind": "time", "label": "tiempo de conversación",
        "keywords": ["conversacion", "hablado", "talk", "duracion de llamada"],
    },
    "demora": {
        "column": "AVGCONNWAIT", "kind": "time", "label": "tiempo de demora",
        "keywords": ["demora", "espera", "wait"],
    },
    "abandono": {
        "column": "AVGABNWAIT", "kind": "time", "label": "tiempo de abandono",
        "keywords": ["abandono", "abn"],
    },
}

_MONTHS = {
    "enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4, "mayo": 5, "may": 5, "junio": 6, "jun": 6,
    "julio": 7, "jul": 7, "agosto": 8, "ago": 8, "septiembre": 9, "sep": 9,
    "setiembre": 9, "octubre": 10, "oct": 10, "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12,
}


# ======================================================================
# Result
# ======================================================================

@dataclass
class QueryResult:
    """Outcome of answering a question."""
    answer: str
    value: Any = None
    detail: pd.DataFrame | None = None
    understood: bool = True
    suggestion: str = ""


# ======================================================================
# Text helpers
# ======================================================================

def _norm(text: str) -> str:
    """Lowercase and strip accents for robust matching."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text)


def _fmt_int(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def _fmt_pct(n: float) -> str:
    return f"{n:.2f}%".replace(".", ",")


def _secs_to_time(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _time_to_secs(t: str) -> float | None:
    parts = str(t).strip().split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None


# ======================================================================
# Parsing
# ======================================================================

def _detect_metric(q: str) -> str | None:
    """Identify which metric the question is about."""
    padded = f" {q} "
    for metric_id, spec in METRICS.items():
        for kw in spec["keywords"]:
            if kw in padded:
                return metric_id
    return None


def _detect_date(q: str, available_dates: pd.Series) -> pd.Timestamp | None:
    """Extract a date from the question, if any."""
    if available_dates.empty:
        return None
    years = available_dates.dt.year.unique()
    default_year = int(years[0]) if len(years) else None

    # "15 de junio" / "15 de jun"
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)", q)
    if m:
        day, month_word = int(m.group(1)), m.group(2)
        month = _MONTHS.get(month_word)
        if month and default_year:
            try:
                return pd.Timestamp(year=default_year, month=month, day=day)
            except ValueError:
                return None

    # "15/06" or "15-06" or "15/06/2026"
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", q)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else default_year
        if year and year < 100:
            year += 2000
        try:
            return pd.Timestamp(year=year, month=month, day=day)
        except (ValueError, TypeError):
            return None

    # "15-jun" / "15 jun"
    m = re.search(r"\b(\d{1,2})[\s-]([a-z]{3,})\b", q)
    if m:
        day, month_word = int(m.group(1)), m.group(2)
        month = _MONTHS.get(month_word)
        if month and default_year:
            try:
                return pd.Timestamp(year=default_year, month=month, day=day)
            except ValueError:
                return None

    # bare "el día 15" — only if the period has a single month
    m = re.search(r"\b(?:el\s+)?dia\s+(\d{1,2})\b", q)
    if m and default_year:
        months = available_dates.dt.month.unique()
        if len(months) == 1:
            try:
                return pd.Timestamp(year=default_year, month=int(months[0]),
                                    day=int(m.group(1)))
            except ValueError:
                return None
    return None


def _detect_subject(q: str, skills: list[str], campaigns: list[str]) -> tuple[str | None, str]:
    """Find which skill or campaign the question refers to.

    Returns (name, kind) where kind is 'skill', 'campaign' or ''.
    """
    # Exact substring match first — longest name wins to avoid
    # "Conmutador" matching inside a longer skill name
    candidates: list[tuple[str, str]] = (
        [(s, "skill") for s in skills] + [(c, "campaign") for c in campaigns]
    )
    candidates.sort(key=lambda x: -len(x[0]))

    for name, kind in candidates:
        if _norm(name) in q:
            return name, kind

    # Fuzzy fallback against the question's word n-grams
    words = q.split()
    all_names = {_norm(n): (n, k) for n, k in candidates}
    for size in (4, 3, 2, 1):
        for i in range(len(words) - size + 1):
            frag = " ".join(words[i:i + size])
            match = difflib.get_close_matches(frag, list(all_names), n=1, cutoff=0.85)
            if match:
                return all_names[match[0]]
    return None, ""


# ======================================================================
# Main entry point
# ======================================================================

def answer_question(
    question: str,
    skill_dfs: dict[str, pd.DataFrame],
    campaign_map: dict[str, list[str]],
) -> QueryResult:
    """Answer a natural-language question about the loaded data.

    Parameters
    ----------
    question:
        The user's question in Spanish.
    skill_dfs:
        Mapping of skill name → its DataFrame.
    campaign_map:
        Mapping of campaign name → list of skill names it contains.
    """
    if not question or not question.strip():
        return QueryResult("Escribí una pregunta.", understood=False)

    q = _norm(question)

    if not skill_dfs:
        return QueryResult("No hay datos cargados.", understood=False)

    # Build the combined frame once
    frames = []
    for name, df in skill_dfs.items():
        d = df.copy()
        d["_skill"] = name
        frames.append(d)
    combined = pd.concat(frames, ignore_index=True)
    available_dates = combined["date"].dropna() if "date" in combined.columns else pd.Series(dtype="datetime64[ns]")

    # --- Parse the question ---
    metric_id = _detect_metric(q)
    if metric_id is None:
        return QueryResult(
            "No identifiqué qué dato buscás.",
            understood=False,
            suggestion="Probá nombrando la métrica: recibidas, atendidas, "
                       "nivel de atención, conversación, demora o abandono.",
        )

    subject, kind = _detect_subject(q, list(skill_dfs), list(campaign_map))
    target_date = _detect_date(q, available_dates)

    # --- Filter the data ---
    data = combined
    scope = "todas las campañas"
    if kind == "skill":
        data = combined[combined["_skill"] == subject]
        scope = f"la habilidad {subject}"
    elif kind == "campaign":
        members = campaign_map.get(subject, [])
        data = combined[combined["_skill"].isin(members)]
        scope = f"la campaña {subject}"

    if data.empty:
        return QueryResult(f"No encontré datos para {scope}.", understood=True)

    when = "en el período"
    if target_date is not None:
        data = data[data["date"] == target_date]
        when = f"el {target_date.day}/{target_date.month:02d}"
        if data.empty:
            return QueryResult(
                f"No hay registros para {scope} {when}. "
                f"Puede que ese día no haya tenido actividad.",
                understood=True,
            )

    # --- Compute the answer ---
    spec = METRICS[metric_id]

    if spec["kind"] == "sum":
        value = float(data[spec["column"]].sum())
        answer = f"{_fmt_int(value)} {spec['label']} en {scope} {when}."

    elif spec["kind"] == "na":
        total = float(data["TOTALCALLS"].sum())
        att = float(data["TRANSFER"].sum())
        value = (att / total * 100) if total else 0.0
        answer = (f"El nivel de atención de {scope} {when} fue de {_fmt_pct(value)} "
                  f"({_fmt_int(att)} atendidas sobre {_fmt_int(total)} recibidas).")

    else:  # time
        secs = [s for s in (_time_to_secs(t) for t in data[spec["column"]].dropna())
                if s is not None]
        if not secs:
            return QueryResult(f"No hay datos de {spec['label']} para {scope} {when}.")
        value = sum(secs) / len(secs)
        answer = f"El {spec['label']} promedio de {scope} {when} fue {_secs_to_time(value)}."

    # Daily breakdown when no specific date was asked for
    detail = None
    if target_date is None and "date" in data.columns and len(data) > 1:
        grouped = data.groupby("date").agg(
            Recibidas=("TOTALCALLS", "sum"),
            Atendidas=("TRANSFER", "sum"),
        ).reset_index()
        grouped["Nivel de Atención"] = (
            grouped["Atendidas"] / grouped["Recibidas"].replace(0, 1) * 100
        ).round(2)
        grouped = grouped.rename(columns={"date": "Fecha"})
        grouped["Fecha"] = pd.to_datetime(grouped["Fecha"]).dt.strftime("%d/%m/%Y")
        detail = grouped

    return QueryResult(answer=answer, value=value, detail=detail)
