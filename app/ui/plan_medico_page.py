"""Streamlit page for the Plan Medico monthly report."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.data_loader.csv_loader import load_csv
from app.data_loader.skill_mapper import extract_skill_name, extract_period
from app.data_loader.closures_loader import (
    load_and_merge_closures, validate_closures, closures_for_skill,
    top_reasons, total_closures, date_from_filename, describe_coverage,
)
from app.data_loader.agents_loader import (
    load_agents_xlsx, validate_agents, agents_summary, agents_table,
)
from app.chart_engine.plan_medico_charts import (
    chart_pm_daily, chart_top_reasons, save_chart, PM_PURPLE,
)
from app.plugins.contact_center.plugin import ContactCenterPlugin
from app.report_generator.plan_medico_pptx import generate_plan_medico_pptx


# Skills of each section, matched case-insensitively against the file names
PM_TOTAL_SKILLS = ["PM Consultas", "Gipfel PM", "Turnos PM Estudios", "Turnos PM Consulta"]
TURNOS_SKILLS = ["Turnos PM Estudios", "Turnos PM Consulta", "Gipfel PM"]
CONSULTAS_SKILL = "PM Consultas"

_SCHEMA = ContactCenterPlugin().get_schema()

# How the average conversation time is computed.
#   "simple"    -> plain mean of the daily figures (current choice)
#   "ponderado" -> each day weighted by its answered calls
CONVERSACION_MODO = "simple"


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _aggregate(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Aggregate several skill frames into a daily series plus KPI values."""
    if not frames:
        return pd.DataFrame(), {}

    combined = pd.concat(frames, ignore_index=True)
    daily = (combined.groupby("date")
             .agg(TOTALCALLS=("TOTALCALLS", "sum"), TRANSFER=("TRANSFER", "sum"))
             .reset_index())
    daily["PCTATT"] = (daily["TRANSFER"] / daily["TOTALCALLS"].replace(0, 1) * 100).round(2)
    daily = daily.sort_values("date")

    rec = int(daily["TOTALCALLS"].sum())
    att = int(daily["TRANSFER"].sum())

    # Average conversation time (see CONVERSACION_MODO)
    secs = weight = 0.0
    for fr in frames:
        for _, row in fr.iterrows():
            parts = str(row.get("AVGTALKTIME", "")).split(":")
            if len(parts) != 3:
                continue
            try:
                value = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except ValueError:
                continue
            if CONVERSACION_MODO == "ponderado":
                n = float(row.get("TRANSFER") or 0)
                if n <= 0:
                    continue
                secs += value * n
                weight += n
            else:  # simple: every day counts the same
                secs += value
                weight += 1
    avg = int(round(secs / weight)) if weight else 0   # round, do not truncate

    kpis = {
        "recibidas": _fmt(rec),
        "atendidas": _fmt(att),
        "nivel_atencion": f"{att / rec * 100:.2f}%".replace(".", ",") if rec else "-",
        "no_atendidas": _fmt(rec - att),
        "conversacion": f"{avg // 60:02d}:{avg % 60:02d}",
    }
    return daily, kpis


def render():
    """Draw the whole Plan Medico page."""
    st.markdown("""
    <div class="main-header">
        <h1>Reporte Plan Medico</h1>
        <p>Hospital Aleman &middot; Contact Center</p>
    </div>""", unsafe_allow_html=True)

    # ---------------- Step 1: files ----------------
    st.markdown('<h3 class="step-header">1 &middot; Subir archivos</h3>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**CSVs de habilidades** (obligatorio)")
        st.caption("PM Consultas, Gipfel PM, Turnos PM Estudios, Turnos PM Consulta")
        skill_files = st.file_uploader("CSVs de habilidades", type=["csv"],
                                       accept_multiple_files=True, key="pm_skills")
    with c2:
        st.markdown("**Excel de productividad de agentes** (opcional)")
        st.caption("Seccion 3c")
        agents_file = st.file_uploader("Excel de agentes", type=["xlsx", "xlsm"],
                                       accept_multiple_files=False, key="pm_agents")

    st.markdown("**CSVs de cierres diarios** (opcional, Seccion 3b)")
    st.caption("Subi todos los dias del mes: se suman automaticamente. "
               "La fecha se lee del nombre del archivo (ej: cierres_22-07-26).")
    closure_files = st.file_uploader("CSVs de cierres", type=["csv"],
                                     accept_multiple_files=True, key="pm_closures")

    if not skill_files:
        st.info("Subi los CSVs de las habilidades de Plan Medico para empezar.")
        return

    # ---------------- Load skills ----------------
    dfs: dict[str, pd.DataFrame] = {}
    period = "Periodo desconocido"
    for uf in skill_files:
        skill = extract_skill_name(uf.name)
        p = extract_period(uf.name)
        if p and period == "Periodo desconocido":
            period = p[0]
        try:
            content = uf.read(); uf.seek(0)
            tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
            tmp.write(content); tmp.close()
            dfs[skill] = load_csv(Path(tmp.name), schema=_SCHEMA)
        except Exception as e:
            st.error(f"Error al leer {uf.name}: {e}")

    def pick(names):
        low = {k.lower(): v for k, v in dfs.items()}
        return [low[n.lower()] for n in names if n.lower() in low]

    found = [n for n in PM_TOTAL_SKILLS if n.lower() in {k.lower() for k in dfs}]
    missing = [n for n in PM_TOTAL_SKILLS if n not in found]

    st.markdown(f"**Periodo:** {period} &middot; **Habilidades detectadas:** {', '.join(found) or 'ninguna'}")
    if missing:
        st.warning("Faltan habilidades de Plan Medico: " + ", ".join(missing)
                   + ". El reporte se genera igual, pero los totales no seran completos.")
    if not found:
        st.error("Ninguno de los archivos corresponde a una habilidad de Plan Medico.")
        return

    # ---------------- Step 2: indicators ----------------
    st.markdown('<h3 class="step-header">2 &middot; Indicadores</h3>', unsafe_allow_html=True)

    d1, k1 = _aggregate(pick(PM_TOTAL_SKILLS))
    d2, k2 = _aggregate(pick(TURNOS_SKILLS))
    d3, k3 = _aggregate(pick([CONSULTAS_SKILL]))

    cols = st.columns(3)
    for col, name, k in zip(cols, ["Plan Medico Total", "Turnos PM", "PM Consultas"], [k1, k2, k3]):
        with col:
            st.markdown(
                f'<div class="kpi-card"><div class="kpi-label">{name}</div>'
                f'<div class="kpi-value">{k.get("recibidas", "-")}</div>'
                f'<div style="color:#6B7280;font-size:.8rem">NA {k.get("nivel_atencion", "-")}</div></div>',
                unsafe_allow_html=True)

    with st.expander("Detalle por habilidad", expanded=True):
        rows = []
        for n in TURNOS_SKILLS + [CONSULTAS_SKILL]:
            fr = pick([n])
            if not fr:
                continue
            _, kk = _aggregate(fr)
            rows.append({"Habilidad": n, "Recibidas": kk["recibidas"],
                         "Atendidas": kk["atendidas"], "NA": kk["nivel_atencion"],
                         "Conv. prom.": kk["conversacion"]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ---------------- Closures ----------------
    closures_ctx = None
    if closure_files:
        paths, names = [], []
        for uf in closure_files:
            content = uf.read(); uf.seek(0)
            tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
            tmp.write(content); tmp.close()
            paths.append(Path(tmp.name))
            names.append(uf.name)

        # The date of each day comes from its file name
        coverage = describe_coverage([date_from_filename(n) for n in names])

        cl = load_and_merge_closures(paths, names=names)
        ok, errs = validate_closures(cl)
        if not ok:
            st.error("Cierres: " + "; ".join(errs))
        else:
            pm_cl = closures_for_skill(cl, CONSULTAS_SKILL)
            n_cl = total_closures(pm_cl)

            detalle = f"{len(closure_files)} archivo(s)"
            if coverage["days"]:
                dias = sorted({d for d in coverage["days"]})
                detalle += (f" &middot; {len(dias)} dia(s) "
                            f"del {dias[0].strftime('%d/%m')} al {dias[-1].strftime('%d/%m')}")
            st.success(f"Cierres cargados: {detalle} &middot; "
                       f"{_fmt(total_closures(cl))} cierres en total &middot; "
                       f"{_fmt(n_cl)} en PM Consultas")

            if coverage["duplicates"]:
                st.warning("Hay archivos repetidos del mismo dia: "
                           + ", ".join(d.strftime("%d/%m/%Y") for d in coverage["duplicates"])
                           + ". Esos cierres se estan contando dos veces.")
            if coverage["unknown"]:
                st.warning(f"{coverage['unknown']} archivo(s) sin fecha reconocible en el "
                           "nombre. Se suman igual, pero no puedo verificar que dia cubren.")
            if coverage["missing_weekdays"]:
                st.info("Dias habiles sin archivo de cierres: "
                        + ", ".join(str(d) for d in coverage["missing_weekdays"])
                        + ". Si el Contact Center opero esos dias, faltan cierres.")

            if n_cl:
                closures_ctx = {"data": pm_cl, "total": n_cl,
                                "dias": len(set(coverage["days"]))}
            else:
                st.warning("No hay cierres de la habilidad PM Consultas en esos archivos.")

    # ---------------- Agents ----------------
    agents_ctx = None
    if agents_file is not None:
        try:
            content = agents_file.read(); agents_file.seek(0)
            tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            tmp.write(content); tmp.close()
            ag = load_agents_xlsx(Path(tmp.name))
            ok, errs = validate_agents(ag)
            if not ok:
                st.error("Agentes: " + "; ".join(errs))
            else:
                summary = agents_summary(ag)
                rows = agents_table(ag)
                st.success(f"Agentes cargados: {summary['operadores']} operadores &middot; "
                           f"{_fmt(summary['atendidas'])} atendidas &middot; "
                           f"{_fmt(summary['cierres'])} cierres")
                agents_ctx = {"summary": summary, "rows": rows}
        except Exception as e:
            st.error(f"Error al leer el Excel de agentes: {e}")

    # ---------------- Step 3: generate ----------------
    st.markdown('<h3 class="step-header">3 &middot; Generar reporte</h3>', unsafe_allow_html=True)

    if not st.button("Generar reporte PPTX", type="primary", use_container_width=True):
        return

    with st.spinner("Generando..."):
        cdir = Path(tempfile.mkdtemp())

        c1p = str(save_chart(chart_pm_daily(
            d1, f"Plan Medico Total - Distribucion diaria ({period})"), cdir / "s1.png")) if len(d1) else None
        c2p = str(save_chart(chart_pm_daily(
            d2, f"Turnos Plan Medico - Distribucion diaria ({period})"), cdir / "s2.png")) if len(d2) else None
        c3p = str(save_chart(chart_pm_daily(
            d3, f"Plan Medico Consultas - Distribucion diaria ({period})",
            bar_color=PM_PURPLE), cdir / "s3.png")) if len(d3) else None

        table_rows = []
        for n in TURNOS_SKILLS:
            fr = pick([n])
            if not fr:
                continue
            _, kk = _aggregate(fr)
            table_rows.append([n, kk["recibidas"], kk["atendidas"],
                               kk["nivel_atencion"], kk["conversacion"]])
        if k2:
            table_rows.append(["TOTAL Turnos PM", k2["recibidas"], k2["atendidas"],
                               k2["nivel_atencion"], k2["conversacion"]])

        closures_arg = None
        if closures_ctx:
            tr = top_reasons(closures_ctx["data"], 10)
            atendidas_ref = (_fmt(agents_ctx["summary"]["atendidas"])
                             if agents_ctx else k3.get("atendidas", "-"))
            cpath = str(save_chart(chart_top_reasons(
                tr["CODE_DESC"].tolist(), tr["cierres"].tolist(), tr["pct"].tolist(),
                f"PM Consultas - Top 10 motivos de cierre "
                f"({_fmt(closures_ctx['total'])} cierres)"), cdir / "s4.png"))
            closures_arg = {
                "subtitle": f"Habilidad PM Consultas: {_fmt(closures_ctx['total'])} "
                            f"cierres sobre {atendidas_ref} atendidas",
                "chart": cpath,
            }

        agents_arg = None
        if agents_ctx:
            rows = list(agents_ctx["rows"])
            s = agents_ctx["summary"]
            rows.append({
                "operador": f"TOTAL ({s['operadores']} ops)",
                "logueo": s["logueo"], "no_disponible": s["no_disponible"],
                "pct_no_disponible": f"{s['pct_no_disponible']}%".replace(".", ","),
                "atendidas": _fmt(s["atendidas"]), "cierres": _fmt(s["cierres"]),
                "utilizacion": "-", "ocupacion": "-",
            })
            agents_arg = {"summary": s, "rows": rows}

        pptx = generate_plan_medico_pptx(
            period=period,
            headline={"pm_total": k1.get("recibidas", "-"),
                      "turnos_pm": k2.get("recibidas", "-"),
                      "pm_consultas": k3.get("recibidas", "-")},
            section1={"subtitle": "Habilidades incluidas: " + " + ".join(found),
                      "kpis": k1, "chart": c1p},
            section2={"subtitle": "Habilidades incluidas: " + " + ".join(
                          [n for n in TURNOS_SKILLS if n in found]),
                      "kpis": k2, "chart": c2p,
                      "table": {"x": (13.333 - 9.6) / 2,
                                "widths": [3.4, 1.6, 1.6, 1.6, 1.4],
                                "headers": ["Habilidad", "Recibidas", "Atendidas",
                                            "NA / % Atencion", "Conv. prom."],
                                "rows": table_rows} if table_rows else None},
            section3a={"subtitle": "Habilidad: PM Consultas", "kpis": k3, "chart": c3p},
            closures=closures_arg,
            agents=agents_arg,
        )

    st.success("Reporte generado")
    st.download_button(
        "Descargar reporte PPTX", data=pptx,
        file_name=f"Reporte_PlanMedico_{period.replace(' ', '_')}.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        type="primary", use_container_width=True)
