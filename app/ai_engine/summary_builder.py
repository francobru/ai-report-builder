"""Rule-based executive summary and conclusions \u2014 no AI API required.

Builds the narrative text directly from the computed KPIs using templates.
Advantages over an LLM for this specific use case:
  - Free, forever
  - No data leaves the application (relevant for hospital data)
  - Deterministic: it can never invent or misstate a number

The wording follows the structure of the original monthly report.
"""

from __future__ import annotations


def _dir_word(variation: dict | None, up: str, down: str, flat: str = "se mantuvo estable") -> str:
    """Return a verb phrase describing the direction of a variation."""
    if not variation or variation.get("variation_pct") is None:
        return ""
    d = variation.get("direction")
    if d == "up":
        return up
    if d == "down":
        return down
    return flat


def _clean_pct(variation: dict | None) -> str:
    """Return the magnitude of a variation without the arrow, e.g. '7,37%'."""
    if not variation:
        return ""
    txt = str(variation.get("formatted", ""))
    return txt.replace("\u25b2", "").replace("\u25bc", "").strip()


def build_executive_summary(
    period: str,
    kpis: dict[str, dict],
    variations: dict[str, dict] | None = None,
    campaign_kpis: dict[str, dict] | None = None,
    previous_period: str | None = None,
    skill_kpis: dict[str, dict] | None = None,
) -> str:
    """One bulleted synthesis of the period.

    Replaces the earlier prose summary plus a separate conclusions block:
    the two repeated the same figures. Each bullet covers a different angle.
    No service-level target is assumed -- none has been agreed -- so the
    text describes and ranks instead of judging.
    """
    variations = variations or {}
    campaign_kpis = campaign_kpis or {}
    skill_kpis = skill_kpis or {}
    ref = previous_period or "el mes anterior"
    B = "\u2022 "
    lines: list[str] = []

    lines.append(f"{B}Durante {period} se recibieron "
                 f"{kpis['recibidas']['formatted']} llamadas y se atendieron "
                 f"{kpis['atendidas']['formatted']}, con un nivel de atenci\u00f3n "
                 f"de {kpis['nivel_atencion']['formatted']}.")

    lines.append(f"{B}El promedio diario fue de "
                 f"{kpis['promedio_recibidas']['formatted']} llamadas recibidas y "
                 f"{kpis['promedio_atendidas']['formatted']} atendidas.")

    var_rec = variations.get("recibidas")
    var_na = variations.get("nivel_atencion")
    partes = []
    if var_rec and var_rec.get("variation_pct") is not None:
        if var_rec.get("direction") == "neutral":
            partes.append("el volumen de llamadas se mantuvo estable")
        else:
            verbo = _dir_word(var_rec, "aument\u00f3", "disminuy\u00f3")
            partes.append(f"el volumen de llamadas {verbo} {_clean_pct(var_rec)}")
    if var_na and var_na.get("variation_pct") is not None:
        if var_na.get("direction") == "neutral":
            partes.append("el nivel de atenci\u00f3n se mantuvo estable")
        else:
            verbo = _dir_word(var_na, "mejor\u00f3", "descendi\u00f3")
            partes.append(f"el nivel de atenci\u00f3n {verbo} {_clean_pct(var_na)}")
    # Both unchanged reads better as one phrase than "se mantuvo estable"
    # repeated twice.
    _quietos = (var_rec and var_rec.get("direction") == "neutral"
                and var_na and var_na.get("direction") == "neutral")
    if _quietos:
        lines.append(f"{B}Respecto a {ref}, tanto el volumen de llamadas como el "
                     f"nivel de atenci\u00f3n se mantuvieron estables.")
    elif partes:
        # "p.p." already ends in a period, so do not add a second one
        texto = f"{B}Respecto a {ref}, " + " y ".join(partes)
        lines.append(texto if texto.endswith(".") else texto + ".")

    if campaign_kpis:
        top = max(campaign_kpis.items(), key=lambda kv: kv[1]["recibidas"]["value"])
        total = sum(k["recibidas"]["value"] for k in campaign_kpis.values())
        share = (top[1]["recibidas"]["value"] / total * 100) if total else 0
        lines.append(f"{B}{top[0]} concentr\u00f3 el {share:.0f}% del volumen "
                     f"({top[1]['recibidas']['formatted']} llamadas recibidas).")

    if len(campaign_kpis) >= 2:
        orden = sorted(campaign_kpis.items(),
                       key=lambda kv: kv[1]["nivel_atencion"]["value"])
        peor, mejor = orden[0], orden[-1]
        lines.append(f"{B}El nivel de atenci\u00f3n por campa\u00f1a vari\u00f3 entre "
                     f"{peor[1]['nivel_atencion']['formatted']} ({peor[0]}) y "
                     f"{mejor[1]['nivel_atencion']['formatted']} ({mejor[0]}).")

    relevantes = [(sk, kk) for sk, kk in skill_kpis.items()
                  if kk["recibidas"]["value"] >= 100]
    if len(relevantes) >= 5:
        relevantes.sort(key=lambda kv: kv[1]["nivel_atencion"]["value"])
        detalle = ", ".join(f"{sk} ({kk['nivel_atencion']['formatted']})"
                            for sk, kk in relevantes[:3])
        lines.append(f"{B}Las habilidades con menor nivel de atenci\u00f3n fueron: "
                     f"{detalle}.")

    conv = kpis.get("tiempo_conversacion", {}).get("formatted")
    dem = kpis.get("tiempo_demora", {}).get("formatted")
    aba = kpis.get("tiempo_abandono", {}).get("formatted")
    if conv and dem:
        extra = f" y {aba} de abandono" if aba else ""
        lines.append(f"{B}Los tiempos promedio fueron de {conv} de conversaci\u00f3n, "
                     f"{dem} de demora{extra}.")

    return "\n".join(lines)


def build_prompt_for_manual_ai(
    period: str,
    kpi_summary: str,
) -> str:
    """Build a ready-to-paste prompt so the user can run it in claude.ai manually.

    Lets the user leverage an existing chat subscription instead of paying
    for API access.
    """
    return (
        f"Sos un analista de datos del Hospital Alem\u00e1n. Redact\u00e1 un resumen ejecutivo "
        f"de m\u00e1ximo 4 oraciones y luego 4 conclusiones breves sobre la productividad "
        f"del Contact Center de {period}.\n\n"
        f"Basate exclusivamente en estos indicadores:\n\n{kpi_summary}\n\n"
        f"Us\u00e1 un tono profesional y neutro. No inventes ning\u00fan dato que no est\u00e9 arriba."
    )
