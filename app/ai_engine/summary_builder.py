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
) -> str:
    """Compose an executive summary from the KPI values."""
    variations = variations or {}
    campaign_kpis = campaign_kpis or {}

    recibidas = kpis["recibidas"]["formatted"]
    atendidas = kpis["atendidas"]["formatted"]
    na = kpis["nivel_atencion"]["formatted"]
    prom_rec = kpis["promedio_recibidas"]["formatted"]

    parts: list[str] = []

    # Opening: volume
    opening = (f"Durante {period} el Contact Center recibi\u00f3 {recibidas} llamadas "
               f"y atendi\u00f3 {atendidas}, alcanzando un nivel de atenci\u00f3n de {na}. "
               f"El promedio diario de llamadas recibidas fue de {prom_rec}.")
    parts.append(opening)

    # Variation vs previous month
    ref = previous_period or "el mes anterior"
    var_rec = variations.get("recibidas")
    var_na = variations.get("nivel_atencion")

    if var_rec or var_na:
        frases = []
        if var_rec and var_rec.get("variation_pct") is not None:
            verbo = _dir_word(var_rec, "aument\u00f3", "disminuy\u00f3")
            frases.append(f"el volumen de llamadas recibidas {verbo} {_clean_pct(var_rec)} respecto a {ref}")
        if var_na and var_na.get("variation_pct") is not None:
            verbo = _dir_word(var_na, "mejor\u00f3", "descendi\u00f3")
            frases.append(f"el nivel de atenci\u00f3n {verbo} {_clean_pct(var_na)}")
        if frases:
            texto = "En la comparaci\u00f3n mensual, " + " y ".join(frases)
            parts.append(texto if texto.endswith(".") else texto + ".")

    # Campaign with the highest volume
    if campaign_kpis:
        top = max(campaign_kpis.items(), key=lambda kv: kv[1]["recibidas"]["value"])
        parts.append(f"La campa\u00f1a de mayor volumen fue {top[0]}, "
                     f"con {top[1]['recibidas']['formatted']} llamadas recibidas y un nivel "
                     f"de atenci\u00f3n de {top[1]['nivel_atencion']['formatted']}.")

    return " ".join(parts)


def build_conclusions(
    period: str,
    kpis: dict[str, dict],
    variations: dict[str, dict] | None = None,
    campaign_kpis: dict[str, dict] | None = None,
    skill_kpis: dict[str, dict] | None = None,
    na_target: float = 85.0,
) -> str:
    """Compose a bulleted conclusions block from the KPI values."""
    variations = variations or {}
    campaign_kpis = campaign_kpis or {}
    skill_kpis = skill_kpis or {}

    lines: list[str] = []

    # 1. Overall attention level vs target
    na_val = kpis["nivel_atencion"]["value"]
    na_fmt = kpis["nivel_atencion"]["formatted"]
    if na_val >= 90:
        lines.append(f"\u2022 El nivel de atenci\u00f3n general de {na_fmt} se ubica en un rango "
                     f"satisfactorio, por encima del objetivo de {na_target:.0f}%.")
    elif na_val >= na_target:
        lines.append(f"\u2022 El nivel de atenci\u00f3n general de {na_fmt} supera el objetivo de "
                     f"{na_target:.0f}%, aunque con margen de mejora.")
    else:
        lines.append(f"\u2022 El nivel de atenci\u00f3n general de {na_fmt} se encuentra por debajo "
                     f"del objetivo de {na_target:.0f}%, lo que requiere atenci\u00f3n.")

    # 2. Volume trend
    var_rec = variations.get("recibidas")
    if var_rec and var_rec.get("variation_pct") is not None:
        verbo = _dir_word(var_rec, "un incremento", "una reducci\u00f3n")
        lines.append(f"\u2022 El volumen de llamadas present\u00f3 {verbo} del "
                     f"{_clean_pct(var_rec)} respecto al mes anterior.")

    # 3. Campaigns below target
    bajo = [(c, k) for c, k in campaign_kpis.items()
            if k["nivel_atencion"]["value"] < na_target]
    if bajo:
        bajo.sort(key=lambda kv: kv[1]["nivel_atencion"]["value"])
        detalle = ", ".join(f"{c} ({k['nivel_atencion']['formatted']})" for c, k in bajo)
        lines.append(f"\u2022 Campa\u00f1as por debajo del objetivo de atenci\u00f3n: {detalle}.")
    elif campaign_kpis:
        lines.append("\u2022 Todas las campa\u00f1as alcanzaron o superaron el objetivo de nivel de atenci\u00f3n.")

    # 4. Best performing campaign
    if campaign_kpis:
        mejor = max(campaign_kpis.items(), key=lambda kv: kv[1]["nivel_atencion"]["value"])
        lines.append(f"\u2022 {mejor[0]} registr\u00f3 el mejor nivel de atenci\u00f3n del per\u00edodo "
                     f"({mejor[1]['nivel_atencion']['formatted']}).")

    # 5. Skills needing review
    if skill_kpis:
        criticas = [(s, k) for s, k in skill_kpis.items()
                    if k["nivel_atencion"]["value"] < na_target
                    and k["recibidas"]["value"] >= 100]
        if criticas:
            criticas.sort(key=lambda kv: kv[1]["nivel_atencion"]["value"])
            top3 = ", ".join(f"{s} ({k['nivel_atencion']['formatted']})"
                             for s, k in criticas[:3])
            lines.append(f"\u2022 Habilidades con mayor oportunidad de mejora: {top3}.")

    # 6. Operational times
    conv = kpis.get("tiempo_conversacion", {}).get("formatted")
    dem = kpis.get("tiempo_demora", {}).get("formatted")
    if conv and dem:
        lines.append(f"\u2022 Los tiempos operativos promedio fueron de {conv} de conversaci\u00f3n "
                     f"y {dem} de demora.")

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
