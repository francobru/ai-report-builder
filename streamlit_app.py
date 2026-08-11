"""AI Report Builder v1.9 \u2014 Aplicaci\u00f3n Web.

Cambios v1.9:
- Selector de habilidades (pod\u00e9s incluir/excluir cada una)
- Promedio diario correcto (total / d\u00edas con actividad)
- Slide de Datos Generales redise\u00f1ada (2 filas, tarjetas grandes centradas)
- Anexos con tablas diarias por campa\u00f1a
"""

import sys
import tempfile
from pathlib import Path

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.data_loader.csv_loader import load_csv
from app.data_loader.validator import validate
from app.data_loader.skill_mapper import (
    extract_skill_name, extract_period, find_campaign,
    classify_files, is_gipfel_skill, CAMPAIGN_ORDER, GIPFEL_SKILLS,
)
from app.kpi_engine.calculator import compute_kpis, compute_variation
from app.chart_engine.renderer import (
    chart_daily_distribution, chart_donut,
    chart_grouped_bar_line, chart_horizontal_bars,
    chart_vertical_bars, save_chart,
)
from app.chart_engine.chart_styles import apply_global_style
from app.plugins.contact_center.plugin import ContactCenterPlugin
from app.report_generator.pptx_python import generate_pptx_report

apply_global_style()
plugin = ContactCenterPlugin()
schema = plugin.get_schema()
kpi_defs = plugin.get_kpis()

# ======================================================================
# Page config
# ======================================================================
st.set_page_config(page_title="AI Report Builder", page_icon="\u2695\ufe0f", layout="wide")

from app.ui.theme import (inject_css, masthead, step as ha_step,
                          card as ha_card, chip as ha_chip, _render as ha_render)

inject_css()

# Report type is chosen first: each type renders its own page.
with st.sidebar:
    st.markdown("#### Reporte")
    _report_type = st.selectbox(
        "Tipo de reporte",
        ["Productividad del Contact Center", "Productividad Mensual Plan Medico"],
    )

if _report_type == "Productividad Mensual Plan Medico":
    from app.ui.plan_medico_page import render as _render_plan_medico
    _render_plan_medico()
    st.stop()

masthead("Productividad del Contact Center",
         "Genera el reporte mensual a partir de los CSV de Tecnovoz")

# Version banner \u2014 lets you confirm at a glance which version is deployed
APP_VERSION = "3.3.3"
st.caption(f"Versi\u00f3n {APP_VERSION} \u00b7 Dos tipos de reporte: Contact Center y Plan Medico")

with st.sidebar:
    st.markdown("#### Como funciona")
    st.markdown(
        "1. Sub\u00ed los **CSVs del mes actual**\n"
        "2. *(Opcional)* Sub\u00ed tambi\u00e9n los del **mes anterior**\n"
        "3. **Seleccion\u00e1** las habilidades a incluir\n"
        "4. Revis\u00e1 los KPIs\n"
        "5. Descarg\u00e1 el PPTX"
    )
    st.divider()
    st.markdown("#### Resumen con IA")
    st.caption("Opcional. Genera resumen ejecutivo y conclusiones.")
    _default_key = ""
    try:
        _default_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    api_key_input = st.text_input(
        "API key de Anthropic", value=_default_key, type="password",
        help="Se obtiene en console.anthropic.com. Si no la carg\u00e1s, el reporte se genera igual pero sin los textos de IA.",
    )
    st.divider()
    st.caption(f"v{APP_VERSION} \u00b7 Selecci\u00f3n + anexos + salientes + tendencia")

# ======================================================================
# Step 1: Upload
# ======================================================================
ha_step(1, "Subir los archivos CSV")

col_cur, col_prev = st.columns(2)
with col_cur:
    st.markdown("**Mes actual** \u00b7 obligatorio")
    current_files = st.file_uploader("CSVs del mes a reportar", type=["csv"],
                                      accept_multiple_files=True, key="current")
with col_prev:
    st.markdown("**Mes anterior** \u00b7 opcional, para comparar")
    previous_files = st.file_uploader("CSVs del mes anterior", type=["csv"],
                                       accept_multiple_files=True, key="previous")

st.markdown("**Llamadas salientes** \u00b7 opcional, archivo aparte")
outbound_file = st.file_uploader("CSV de llamadas salientes", type=["csv"],
                                  accept_multiple_files=False, key="outbound")

if not current_files:
    st.info("Sub\u00ed los archivos CSV del mes que quer\u00e9s reportar para empezar.")
    st.stop()

# ======================================================================
# Load helper
# ======================================================================
def load_file_set(uploaded_files):
    dfs = {}
    period_label = None
    for uf in uploaded_files:
        skill = extract_skill_name(uf.name)
        if period_label is None:
            p = extract_period(uf.name)
            if p:
                period_label = p[0]
        try:
            content = uf.read(); uf.seek(0)
            tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
            tmp.write(content); tmp.close()
            dfs[skill] = load_csv(Path(tmp.name), schema=schema)
        except Exception as e:
            st.error(f"Error cargando {uf.name}: {e}")
    return dfs, period_label or "Per\u00edodo desconocido"


all_current_dfs, current_period = load_file_set(current_files)
prev_dfs, prev_period = (({}, None) if not previous_files else load_file_set(previous_files))

# ======================================================================
# Step 2: Skill selection
# ======================================================================
ha_step(2, "Elegir las habilidades que entran al reporte")

# Init session state for selections
if "skill_selection" not in st.session_state:
    st.session_state.skill_selection = {}

# The selector covers the UNION of both months, so a skill that only exists in
# the previous month (e.g. Laboratorio) can also be excluded. Whatever is
# unchecked is removed from BOTH months -- report and comparison stay in sync.
all_skills = sorted(set(all_current_dfs) | set(prev_dfs))
skills_key = tuple(all_skills)
if st.session_state.get("_skills_key") != skills_key:
    st.session_state.skill_selection = {s: True for s in all_skills}
    st.session_state._skills_key = skills_key

col_all, col_none, col_info = st.columns([1, 1, 3])
with col_all:
    if st.button("Seleccionar todas", use_container_width=True):
        for s in all_skills:
            st.session_state.skill_selection[s] = True
        st.rerun()
with col_none:
    if st.button("Deseleccionar todas", use_container_width=True):
        for s in all_skills:
            st.session_state.skill_selection[s] = False
        st.rerun()
with col_info:
    n_selected = sum(1 for s in all_skills if st.session_state.skill_selection.get(s))
    st.markdown(f"**{n_selected} de {len(all_skills)}** habilidades seleccionadas")

if prev_dfs:
    st.caption("Lo que destildes se excluye del reporte Y de la comparacion "
               "con el mes anterior.")

classification_all = {}
for skill in all_skills:
    camp = find_campaign(skill)
    classification_all.setdefault(camp, []).append({"skill": skill})

for camp_name in CAMPAIGN_ORDER + ["Camp HA", "Sin asignar"]:
    if camp_name not in classification_all:
        continue
    skills = classification_all[camp_name]
    ha_render(ha_chip(camp_name, muted=(camp_name == "Sin asignar")))

    cols = st.columns(4)
    for i, sk in enumerate(skills):
        skill_name = sk["skill"]
        # Mark skills that are not present in both months
        if prev_dfs:
            in_cur, in_prev = skill_name in all_current_dfs, skill_name in prev_dfs
            if in_cur and not in_prev:
                label = f"{skill_name}  (solo {current_period})"
            elif in_prev and not in_cur:
                label = f"{skill_name}  (solo {prev_period})"
            else:
                label = skill_name
        else:
            label = skill_name
        with cols[i % 4]:
            st.session_state.skill_selection[skill_name] = st.checkbox(
                label,
                value=st.session_state.skill_selection.get(skill_name, True),
                key=f"chk_{skill_name}",
            )

# Apply the selection to BOTH months
current_dfs = {s: df for s, df in all_current_dfs.items()
               if st.session_state.skill_selection.get(s, False)}
prev_dfs = {s: df for s, df in prev_dfs.items()
            if st.session_state.skill_selection.get(s, False)}

if not current_dfs:
    st.warning("\u26a0\ufe0f No hay habilidades seleccionadas. Marc\u00e1 al menos una para generar el reporte.")
    st.stop()

# ======================================================================
# Compute
# ======================================================================
all_current = pd.concat([df.assign(_skill=n) for n, df in current_dfs.items()], ignore_index=True)
no_gipfel_mask = ~all_current["_skill"].str.lower().isin(GIPFEL_SKILLS)
all_no_gipfel = all_current[no_gipfel_mask]

global_kpis = compute_kpis(all_current, kpi_defs)
global_ng_kpis = compute_kpis(all_no_gipfel, kpi_defs) if len(all_no_gipfel) > 0 else None

# Variations
# The variation compares FULL month totals against FULL month totals, so it
# always matches the figure shown on the KPI card. (Filtering the baseline to
# only the skills common to both months made the percentage disagree with a
# hand calculation done from the report totals.)
global_variations = {}
global_ng_variations = {}
solo_mes_anterior = []
solo_mes_actual = []
if prev_dfs:
    solo_mes_anterior = sorted(set(prev_dfs) - set(current_dfs))
    solo_mes_actual = sorted(set(current_dfs) - set(prev_dfs))

    all_prev = pd.concat([df.assign(_skill=n) for n, df in prev_dfs.items()],
                          ignore_index=True)
    prev_kpis = compute_kpis(all_prev, kpi_defs)
    global_variations = compute_variation(global_kpis, prev_kpis)

    # Same comparison but excluding Gipfel skills, for the "sin Gipfel" slide
    prev_ng = all_prev[~all_prev["_skill"].str.lower().isin(GIPFEL_SKILLS)]
    if global_ng_kpis is not None and len(prev_ng) > 0:
        prev_ng_kpis = compute_kpis(prev_ng, kpi_defs)
        global_ng_variations = compute_variation(global_ng_kpis, prev_ng_kpis)

# Per-campaign KPIs + variations
classification = {}
for skill in current_dfs.keys():
    camp = find_campaign(skill)
    classification.setdefault(camp, []).append({"skill": skill})
campaign_kpis = {}
campaign_variations = {}
campaign_dfs = {}
for camp_name in CAMPAIGN_ORDER + ["Camp HA"]:
    if camp_name not in classification:
        continue
    skills = [s["skill"] for s in classification[camp_name] if s["skill"] in current_dfs]
    if not skills:
        continue
    camp_df = pd.concat([current_dfs[s] for s in skills], ignore_index=True)
    campaign_dfs[camp_name] = camp_df
    campaign_kpis[camp_name] = compute_kpis(camp_df, kpi_defs)

    if prev_dfs:
        # All skills of this campaign that exist in the previous month,
        # regardless of whether they were also uploaded for the current one.
        prev_skills = [s for s in prev_dfs if find_campaign(s) == camp_name]
        if prev_skills:
            prev_camp_df = pd.concat([prev_dfs[s] for s in prev_skills], ignore_index=True)
            prev_camp_kpis = compute_kpis(prev_camp_df, kpi_defs)
            campaign_variations[camp_name] = compute_variation(campaign_kpis[camp_name],
                                                                 prev_camp_kpis)

skill_kpis = {n: compute_kpis(df, kpi_defs) for n, df in current_dfs.items()}

# ======================================================================
# Step 3: KPIs
# ======================================================================
ha_step(3, "Revisar los indicadores")

if prev_dfs and (solo_mes_anterior or solo_mes_actual):
    _msg = []
    if solo_mes_anterior:
        _msg.append(f"solo en {prev_period}: {', '.join(solo_mes_anterior)}")
    if solo_mes_actual:
        _msg.append(f"solo en {current_period}: {', '.join(solo_mes_actual)}")
    st.info("Las habilidades no coinciden entre los dos meses (" + "; ".join(_msg) +
            "). Se comparan igual: el total de lo seleccionado en cada mes. "
            "Si no quer\u00e9s que una habilidad entre en la comparacion, "
            "destildala en el paso 2.")


def render_kpi_card(label, value, color=None, variation=None):
    """Metric card. `color` is accepted for call compatibility and ignored:
    the theme owns the palette so every card matches."""
    var = ""
    if variation and variation.get("formatted", "\u2014") != "\u2014":
        var = variation["formatted"]
    return ha_card(label, value, variation=var, accent=bool(var))

st.markdown(f"#### Todas las campa\u00f1as seleccionadas \u2014 {current_period}"
            + (f" vs {prev_period}" if prev_dfs else ""))

# Row 1: 2 big cards
cols_top = st.columns(2)
with cols_top[0]:
    ha_render(render_kpi_card("Recibidas", global_kpis["recibidas"]["formatted"],
                                 "#1B3A5C", global_variations.get("recibidas")))
with cols_top[1]:
    ha_render(render_kpi_card("Atendidas", global_kpis["atendidas"]["formatted"],
                                 "#5B9BD5", global_variations.get("atendidas")))

# Row 2: 3 cards
cols_bot = st.columns(3)
with cols_bot[0]:
    ha_render(render_kpi_card("Prom. Diario Recibidas",
                                 global_kpis["promedio_recibidas"]["formatted"],
                                 "#7F8C8D"))
with cols_bot[1]:
    ha_render(render_kpi_card("Prom. Diario Atendidas",
                                 global_kpis["promedio_atendidas"]["formatted"],
                                 "#7F8C8D"))
with cols_bot[2]:
    ha_render(render_kpi_card("Nivel de Atenci\u00f3n",
                                 global_kpis["nivel_atencion"]["formatted"],
                                 "#4CAF50", global_variations.get("nivel_atencion")))

# Time cards
st.markdown("")
time_cols = st.columns(3)
for col, kid, lab in zip(time_cols,
    ["tiempo_conversacion", "tiempo_demora", "tiempo_abandono"],
    ["Conversaci\u00f3n", "Demora", "Abandono"]):
    with col:
        ha_render(render_kpi_card(lab, global_kpis[kid]["formatted"], "#1B3A5C"))

# Campaign KPIs
with st.expander("KPIs por campa\u00f1a" + (" (con variaciones)" if prev_dfs else ""), expanded=True):
    for camp_name in CAMPAIGN_ORDER + ["Camp HA"]:
        if camp_name not in campaign_kpis:
            continue
        ck = campaign_kpis[camp_name]
        cv = campaign_variations.get(camp_name, {})
        parts = [f"**{camp_name}** \u2014"]
        for kid, lab in [("recibidas", "Rec"), ("atendidas", "At"), ("nivel_atencion", "NA")]:
            val = ck[kid]["formatted"]
            vr = cv.get(kid, {}).get("formatted", "")
            arrow = ""
            if vr and "\u25b2" in vr: arrow = ""
            elif vr and "\u25bc" in vr: arrow = ""
            parts.append(f"{lab}: **{val}**{' ' + arrow + ' ' + vr if vr else ''}")
        st.markdown(" \u00b7 ".join(parts))

with st.expander("Detalle por habilidad", expanded=False):
    rows = []
    for name in sorted(current_dfs.keys(), key=lambda n: -skill_kpis[n]["recibidas"]["value"]):
        sk = skill_kpis[name]
        rows.append({
            "Habilidad": name, "Campa\u00f1a": find_campaign(name),
            "Recibidas": sk["recibidas"]["formatted"],
            "Atendidas": sk["atendidas"]["formatted"],
            "NA": sk["nivel_atencion"]["formatted"],
            "Prom Diario Rec": sk["promedio_recibidas"]["formatted"],
            "Prom Diario At": sk["promedio_atendidas"]["formatted"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ======================================================================
# Aggregate helpers
# ======================================================================
def aggregate_daily(df):
    """Aggregate daily rows: sum Recibidas + Atendidas by date, recompute NA."""
    if "date" not in df.columns or len(df) == 0:
        return pd.DataFrame()
    daily = df.groupby("date").agg(
        TOTALCALLS=("TOTALCALLS", "sum"),
        TRANSFER=("TRANSFER", "sum"),
    ).reset_index()
    daily["PCTATT"] = (daily["TRANSFER"] / daily["TOTALCALLS"].replace(0, 1) * 100).round(2)
    return daily.sort_values("date")


def build_annex_rows(daily_df):
    """Convert aggregated daily df to annex row dicts."""
    rows = []
    month_names = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
                   7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}
    for _, r in daily_df.iterrows():
        d = pd.Timestamp(r["date"])
        rows.append({
            "fecha": f"{d.day}-{month_names.get(d.month, '?')}",
            "recibidas": f"{int(r['TOTALCALLS']):,}".replace(",", "."),
            "atendidas": f"{int(r['TRANSFER']):,}".replace(",", "."),
            "na": f"{r['PCTATT']:.2f}%".replace(".", ","),
        })
    return rows


# ======================================================================
# Step 4: Charts
# ======================================================================
ha_step(4, "Generar y descargar el reporte")

chart_dir = Path(tempfile.mkdtemp())
chart_images = {}

# Daily by campaign (aggregated)
daily_by_campaign = {}
for camp_name, camp_df in campaign_dfs.items():
    daily = aggregate_daily(camp_df)
    if len(daily) > 0:
        daily_by_campaign[camp_name] = daily
        key = f"daily_{camp_name.lower().replace(' ', '_').replace('\u00e9', 'e')}"
        fig = chart_daily_distribution(daily, title=f"Distribuci\u00f3n diaria \u2014 {camp_name}")
        chart_images[key] = str(save_chart(fig, chart_dir / f"{key}.png"))
        plt.close(fig)

# All (aggregated across campaigns)
daily_all = aggregate_daily(all_current)
if len(daily_all) > 0:
    fig = chart_daily_distribution(daily_all,
                                    title="Distribuci\u00f3n diaria \u2014 Todas las campa\u00f1as")
    chart_images["daily_all"] = str(save_chart(fig, chart_dir / "daily_all.png"))
    plt.close(fig)

# All no Gipfel
daily_ng = aggregate_daily(all_no_gipfel)
if len(daily_ng) > 0:
    fig = chart_daily_distribution(daily_ng,
                                    title="Distribuci\u00f3n diaria \u2014 Todas las campa\u00f1as (sin Gipfel)")
    chart_images["daily_all_no_gipfel"] = str(save_chart(fig, chart_dir / "daily_ng.png"))
    plt.close(fig)

# Weekday
if len(daily_all) > 0:
    tmp = daily_all.copy()
    tmp["weekday"] = tmp["date"].dt.dayofweek
    wk = tmp.groupby("weekday").agg(rec=("TOTALCALLS", "sum"), att=("TRANSFER", "sum"))
    wk = wk.reindex(range(7), fill_value=0)
    wk["na"] = (wk["att"] / wk["rec"].replace(0, 1) * 100).round(2)
    fig = chart_grouped_bar_line(
        ["lun", "mar", "mi\u00e9", "jue", "vie", "s\u00e1b", "dom"],
        wk["rec"].tolist(), wk["att"].tolist(), wk["na"].tolist(),
        title="Distribuci\u00f3n por d\u00eda de semana")
    chart_images["weekday_distribution"] = str(save_chart(fig, chart_dir / "weekday.png"))
    plt.close(fig)

# Campaign volume + share
camp_sorted = [c for c in CAMPAIGN_ORDER + ["Camp HA"] if c in campaign_kpis]
if camp_sorted:
    rec = [campaign_kpis[c]["recibidas"]["value"] for c in camp_sorted]
    att = [campaign_kpis[c]["atendidas"]["value"] for c in camp_sorted]
    # Horizontal bars include ALL campaigns (Agendas, Camp HA too)
    fig = chart_horizontal_bars(camp_sorted, rec, att, title="Distribuci\u00f3n por campa\u00f1a")
    chart_images["campaign_volume"] = str(save_chart(fig, chart_dir / "camp_vol.png"))
    plt.close(fig)

    # Donut EXCLUDES Agendas and Camp HA (too small; matches original report).
    # Center total = sum of the slices actually shown in the donut.
    donut_campaigns = [c for c in camp_sorted if c not in ("Agendas", "Camp HA")]
    donut_rec = [campaign_kpis[c]["recibidas"]["value"] for c in donut_campaigns]
    donut_total = int(sum(donut_rec))
    total_str = f"{donut_total:,}".replace(",", ".")
    fig = chart_donut(donut_campaigns, donut_rec, title="Participaci\u00f3n por campa\u00f1a",
                      center_value=total_str, center_label="Total recibidas")
    chart_images["campaign_share"] = str(save_chart(fig, chart_dir / "camp_share.png"))
    plt.close(fig)

# Skill top 10
top_skills = sorted(skill_kpis.items(), key=lambda x: -x[1]["recibidas"]["value"])[:10]
if top_skills:
    fig = chart_horizontal_bars(
        [s[0] for s in top_skills],
        [s[1]["recibidas"]["value"] for s in top_skills],
        [s[1]["atendidas"]["value"] for s in top_skills],
        title="Top 10 habilidades por volumen de llamadas recibidas")
    chart_images["skill_volume_top10"] = str(save_chart(fig, chart_dir / "skill_top10.png"))
    plt.close(fig)

# ---- Monthly trend (evoluci\u00f3n mensual) ----
from app.data_loader.monthly_history import get_trend, add_month
from app.data_loader.skill_mapper import extract_period as _extract_period_full

# Determine current month/year from the period label
_period_info = None
for uf in current_files:
    _period_info = _extract_period_full(uf.name)
    if _period_info:
        break

monthly_trend_data = []
if _period_info:
    _, cur_month, cur_year = _period_info
    # Save current month's totals to history (so it accumulates over time)
    add_month(cur_year, cur_month,
              recibidas=int(global_kpis["recibidas"]["value"]),
              atendidas=int(global_kpis["atendidas"]["value"]),
              nivel_atencion=global_kpis["nivel_atencion"]["value"])

    # Also save the PREVIOUS month when its files were uploaded. Otherwise a
    # month the user never generated a report for (or one lost when the server
    # restarted, since its storage is temporary) leaves a hole in the trend.
    if prev_dfs:
        _prev_info = None
        for uf in previous_files:
            _prev_info = _extract_period_full(uf.name)
            if _prev_info:
                break
        if _prev_info:
            _, prev_month, prev_year = _prev_info
            _all_prev = pd.concat(
                [d.assign(_skill=n) for n, d in prev_dfs.items()], ignore_index=True)
            _pk = compute_kpis(_all_prev, kpi_defs)
            add_month(prev_year, prev_month,
                      recibidas=int(_pk["recibidas"]["value"]),
                      atendidas=int(_pk["atendidas"]["value"]),
                      nivel_atencion=_pk["nivel_atencion"]["value"])

    # Build trend up to current month
    trend_records = get_trend(cur_year, cur_month)
    monthly_trend_data = [
        {"month_name": r.month_name, "recibidas": r.recibidas,
         "atendidas": r.atendidas, "nivel_atencion": r.nivel_atencion}
        for r in trend_records
    ]
    # Warn about holes in the series (e.g. a month never reported, or lost when
    # the server restarted). Uploading that month as "mes anterior" fills it.
    _present = {r.month for r in trend_records}
    _missing = [m for m in range(1, cur_month + 1) if m not in _present]
    if _missing:
        _names = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                  7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",
                  11:"Noviembre",12:"Diciembre"}
        st.warning("Faltan meses en la evolucion mensual: "
                   + ", ".join(_names[m] for m in _missing)
                   + ". Para completarlos, genera una vez el reporte de ese mes "
                     "o cargalo como 'mes anterior'.")

    if len(monthly_trend_data) >= 2:
        fig = chart_grouped_bar_line(
            [r["month_name"] for r in monthly_trend_data],
            [r["recibidas"] for r in monthly_trend_data],
            [r["atendidas"] for r in monthly_trend_data],
            [r["nivel_atencion"] for r in monthly_trend_data],
            title=f"Evoluci\u00f3n mensual {cur_year}",
            y_na_min=60.0)
        chart_images["monthly_evolution"] = str(save_chart(fig, chart_dir / "monthly.png"))
        plt.close(fig)

# ---- Outbound calls (llamadas salientes) ----
outbound_data = None
if outbound_file is not None:
    from app.data_loader.outbound_loader import (
        load_outbound_csv, aggregate_outbound, count_rotaciones_am,
    )
    try:
        content = outbound_file.read(); outbound_file.seek(0)
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        tmp.write(content); tmp.close()
        ob_df = load_outbound_csv(Path(tmp.name))
        ob_agg = aggregate_outbound(ob_df)

        outbound_data = {
            "total": ob_agg["total"],
            "rotaciones": count_rotaciones_am(ob_df),
            "solo_operadores": 0,  # refined later with business rule
        }

        # Chart: distribution by result
        if ob_agg["by_result"]:
            results = list(ob_agg["by_result"].keys())
            counts = list(ob_agg["by_result"].values())
            fig = chart_vertical_bars(results, counts, title="Distribuci\u00f3n por resultado")
            chart_images["outbound_result"] = str(save_chart(fig, chart_dir / "ob_result.png"))
            plt.close(fig)

        # Chart: daily distribution
        if len(ob_agg["daily"]) > 0:
            daily_ob = ob_agg["daily"]
            month_names = {1:"ene",2:"feb",3:"mar",4:"abr",5:"may",6:"jun",
                           7:"jul",8:"ago",9:"sep",10:"oct",11:"nov",12:"dic"}
            labels = [f"{pd.Timestamp(d).day}-{month_names.get(pd.Timestamp(d).month,'?')}"
                      for d in daily_ob["date"]]
            fig = chart_vertical_bars(labels, daily_ob["count"].tolist(),
                                      title="Distribuci\u00f3n diaria \u2014 Llamadas salientes")
            chart_images["outbound_daily"] = str(save_chart(fig, chart_dir / "ob_daily.png"))
            plt.close(fig)

        st.success(f"Llamadas salientes cargadas: {ob_agg['total']:,} llamadas".replace(",", "."))
    except Exception as e:
        st.error(f"Error al procesar llamadas salientes: {e}")

# ---- Consultas sobre los datos ----
from app.ai_engine.query_engine import answer_question

with st.expander("Consultar los datos", expanded=False):
    st.caption("Pregunt\u00e1 en lenguaje natural. Por ejemplo: "
               "*cu\u00e1ntas llamadas atendidas el 15 de junio en Turnos PM Estudios*")

    pregunta = st.text_input("Tu pregunta", key="qa_input",
                             placeholder="cu\u00e1ntas atendidas el 15 de junio en Turnos PM Estudios")

    if pregunta:
        _campaign_map = {c: [x["skill"] for x in v] for c, v in classification.items()}
        res = answer_question(pregunta, current_dfs, _campaign_map)
        if res.understood:
            st.success(res.answer)
            if res.detail is not None and len(res.detail) > 1:
                with st.expander("Ver detalle diario"):
                    st.dataframe(res.detail, use_container_width=True, hide_index=True)
        else:
            st.warning(res.answer)
            if res.suggestion:
                st.caption(res.suggestion)

    st.caption("Las respuestas se calculan directamente sobre los CSVs cargados: "
               "son exactas y no se env\u00eda ning\u00fan dato fuera de la aplicaci\u00f3n.")

# ---- Resumen ejecutivo y conclusiones ----
from app.ai_engine.summary_builder import (
    build_executive_summary, build_conclusions, build_prompt_for_manual_ai,
)

ai_texts = {}
with st.expander("Resumen ejecutivo y conclusiones", expanded=True):
    modo = st.radio(
        "\u00bfC\u00f3mo quer\u00e9s generar los textos?",
        ["Autom\u00e1tico (gratis, sin IA)", "Con IA (requiere API key)"],
        horizontal=True,
        help="El modo autom\u00e1tico arma los textos con los n\u00fameros reales del reporte. "
             "No manda datos a ning\u00fan servidor externo y no tiene costo.",
    )

    if modo.startswith("Autom\u00e1tico"):
        resumen_auto = build_executive_summary(
            current_period, global_kpis, global_variations, campaign_kpis, prev_period)
        conclusiones_auto = build_conclusions(
            current_period, global_kpis, global_variations, campaign_kpis, skill_kpis)

        st.markdown("**Resumen ejecutivo**")
        ai_texts["resumen"] = st.text_area("resumen", resumen_auto, height=130,
                                            label_visibility="collapsed")
        st.markdown("**Conclusiones**")
        ai_texts["conclusiones"] = st.text_area("conclusiones", conclusiones_auto, height=180,
                                                 label_visibility="collapsed")
        st.caption("Pod\u00e9s editar los textos antes de generar el reporte.")

        with st.popover("Prefiero ped\u00edrselo a Claude.ai"):
            from app.ai_engine.client import build_kpi_summary
            st.markdown("Copi\u00e1 este texto y pegalo en claude.ai (o el chat que uses). "
                        "Despu\u00e9s peg\u00e1 la respuesta en los campos de arriba.")
            st.code(build_prompt_for_manual_ai(
                current_period, build_kpi_summary(global_kpis, global_variations)),
                language=None)

    else:
        if not api_key_input:
            st.warning("Carg\u00e1 una API key de Anthropic en la barra lateral para usar este modo.")
        else:
            from app.ai_engine.client import AIEngine, build_kpi_summary
            if st.button("Generar textos con IA", use_container_width=True):
                engine = AIEngine(api_key=api_key_input)
                if not engine.is_available:
                    st.error("No se pudo conectar con la IA. Revis\u00e1 la API key.")
                else:
                    prompts = plugin.get_prompts()
                    kpi_summary = build_kpi_summary(global_kpis, global_variations)
                    camp_lines = [
                        f"- {c}: recibidas {campaign_kpis[c]['recibidas']['formatted']}, "
                        f"atendidas {campaign_kpis[c]['atendidas']['formatted']}, "
                        f"NA {campaign_kpis[c]['nivel_atencion']['formatted']}"
                        for c in CAMPAIGN_ORDER if c in campaign_kpis
                    ]
                    full_summary = kpi_summary + "\n\nPor campa\u00f1a:\n" + "\n".join(camp_lines)
                    with st.spinner("Redactando..."):
                        st.session_state["ai_resumen"] = engine.generate_executive_summary(
                            prompts, full_summary, current_period)
                        st.session_state["ai_conclusiones"] = engine.generate_conclusions(
                            prompts, full_summary, current_period)

            if "ai_resumen" in st.session_state:
                st.markdown("**Resumen ejecutivo**")
                ai_texts["resumen"] = st.text_area("resumen", st.session_state["ai_resumen"],
                                                    height=130, label_visibility="collapsed")
                st.markdown("**Conclusiones**")
                ai_texts["conclusiones"] = st.text_area("conclusiones",
                                                         st.session_state["ai_conclusiones"],
                                                         height=180, label_visibility="collapsed")

# Preview
with st.expander("Vista previa de gr\u00e1ficos", expanded=False):
    if "daily_all" in chart_images:
        st.image(chart_images["daily_all"], caption="Distribuci\u00f3n diaria \u2014 Todas las campa\u00f1as")
    for camp_name in CAMPAIGN_ORDER:
        key = f"daily_{camp_name.lower().replace(' ', '_').replace('\u00e9', 'e')}"
        if key in chart_images:
            st.image(chart_images[key], caption=f"Distribuci\u00f3n diaria \u2014 {camp_name}")

# ======================================================================
# Generate PPTX
# ======================================================================
generate_btn = st.button("Generar reporte", type="primary", use_container_width=True)

if generate_btn:
    with st.spinner("Generando reporte..."):
        fmt = lambda kpis: {k: v["formatted"] for k, v in kpis.items()}
        fmt_var = lambda vars: {k: v.get("formatted", "") for k, v in vars.items()} if vars else {}

        pptx_campaigns = []
        pptx_campaigns.append({
            "name": "Todas las Campa\u00f1as", "is_all": True,
            "kpis": fmt(global_kpis),
            "variations": fmt_var(global_variations),
            "chart_path": chart_images.get("daily_all", ""),
        })
        if global_ng_kpis:
            pptx_campaigns.append({
                "name": "Todas las Campa\u00f1as (sin Gipfel)", "is_all": True,
                "kpis": fmt(global_ng_kpis),
                "variations": fmt_var(global_ng_variations),
                "chart_path": chart_images.get("daily_all_no_gipfel", ""),
            })
        for camp_name in CAMPAIGN_ORDER:
            if camp_name not in campaign_kpis:
                continue
            key = f"daily_{camp_name.lower().replace(' ', '_').replace('\u00e9', 'e')}"
            pptx_campaigns.append({
                "name": camp_name,
                "kpis": fmt(campaign_kpis[camp_name]),
                "variations": fmt_var(campaign_variations.get(camp_name)),
                "chart_path": chart_images.get(key, ""),
            })

        pptx_skills = []
        for name in sorted(current_dfs.keys(), key=lambda n: -skill_kpis[n]["recibidas"]["value"]):
            sk = skill_kpis[name]
            pptx_skills.append({
                "name": name,
                "recibidas": sk["recibidas"]["formatted"],
                "atendidas": sk["atendidas"]["formatted"],
                "na": sk["nivel_atencion"]["formatted"],
                "conversacion": sk["tiempo_conversacion"]["formatted"],
                "demora": sk["tiempo_demora"]["formatted"],
                "abandono": sk["tiempo_abandono"]["formatted"],
            })

        # Build annexes (one per campaign with daily data)
        annexes = []
        for camp_name in CAMPAIGN_ORDER + ["Camp HA"]:
            if camp_name in daily_by_campaign:
                annexes.append({
                    "campaign_name": camp_name,
                    "daily_rows": build_annex_rows(daily_by_campaign[camp_name]),
                })

        # Footnote for the donut (campaigns excluded due to low share)
        excluded = [c for c in ("Agendas", "Camp HA") if c in campaign_kpis]
        donut_note = None
        if excluded and camp_sorted:
            total_all = sum(campaign_kpis[c]["recibidas"]["value"] for c in camp_sorted)
            parts = []
            for c in excluded:
                share = campaign_kpis[c]["recibidas"]["value"] / total_all * 100 if total_all else 0
                label = "Agendas M\u00e9dicas" if c == "Agendas" else c
                parts.append(f"{label} ({share:.2f}%".replace(".", ",") + ")")
            donut_note = ("Nota: " + " y ".join(parts) +
                          " no figuran en el gr\u00e1fico de participaci\u00f3n debido a su baja representaci\u00f3n.")

        # Skill \u2192 campaign reference table
        skills_ref = [{"skill": s, "campaign": find_campaign(s)}
                      for s in sorted(current_dfs.keys())]

        pptx_bytes = generate_pptx_report(
            period=current_period,
            global_kpis=fmt(global_kpis),
            global_variations=fmt_var(global_variations),
            campaign_data=pptx_campaigns,
            skill_table=pptx_skills,
            chart_images=chart_images,
            annexes=annexes,
            outbound=outbound_data,
            monthly_trend=monthly_trend_data if monthly_trend_data else None,
            donut_footnote=donut_note,
            skills_reference=skills_ref,
        )

        # Same content, PDF layout
        from app.report_generator.pdf_generator import generate_pdf_report
        pdf_bytes = generate_pdf_report(
            period=current_period,
            global_kpis=fmt(global_kpis),
            global_variations=fmt_var(global_variations),
            campaign_data=pptx_campaigns,
            skill_table=pptx_skills,
            chart_images=chart_images,
            annexes=annexes,
            outbound=outbound_data,
            monthly_trend=monthly_trend_data if monthly_trend_data else None,
            donut_footnote=donut_note,
            skills_reference=skills_ref,
        )

    st.success(f"Reporte generado ({len(pptx_campaigns)} campa\u00f1as, {len(annexes)} anexos)")
    slug = current_period.replace(" ", "_")
    col_pptx, col_pdf = st.columns(2)
    with col_pptx:
        st.download_button(
            label="Descargar PPTX",
            data=pptx_bytes,
            file_name=f"Reporte_CCenter_{slug}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            type="primary", use_container_width=True,
        )
    with col_pdf:
        st.download_button(
            label="Descargar PDF",
            data=pdf_bytes,
            file_name=f"Reporte_CCenter_{slug}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
