"""AI Report Builder v1.3 — Aplicación Web.

Cambios v1.3:
- Selector de habilidades (podés incluir/excluir cada una)
- Promedio diario correcto (total / días con actividad)
- Slide de Datos Generales rediseñada (2 filas, tarjetas grandes centradas)
- Anexos con tablas diarias por campaña
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
st.set_page_config(page_title="AI Report Builder", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1B3A5C 0%, #2C5F8A 100%);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;
    }
    .main-header h1 { color: white !important; font-size: 1.8rem !important; margin: 0 !important; }
    .main-header p { color: #B0BEC5 !important; font-size: 0.95rem !important; margin: .3rem 0 0 !important; }
    .kpi-card {
        background: white; border-radius: 10px; padding: 1rem 1.2rem;
        border: 1px solid #E0E0E0; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.08);
    }
    .kpi-label { color: #7F8C8D; font-size: .75rem; text-transform: uppercase; letter-spacing: .5px; }
    .kpi-value { color: #1B3A5C; font-size: 1.8rem; font-weight: 700; margin: .3rem 0; }
    .kpi-var-up { color: #4CAF50; font-size: .9rem; font-weight: 600; }
    .kpi-var-down { color: #E74C3C; font-size: .9rem; font-weight: 600; }
    .step-header { color: #1B3A5C; border-left: 4px solid #4CAF50; padding-left: 12px; margin: 1.5rem 0 1rem; }
    .camp-badge {
        display: inline-block; padding: 3px 10px; border-radius: 12px;
        font-size: .75rem; font-weight: 600;
    }
    .badge-turnos { background: #E3F2FD; color: #1565C0; }
    .badge-conmutador { background: #E0F2F1; color: #00695C; }
    .badge-plan { background: #F3E5F5; color: #7B1FA2; }
    .badge-portal { background: #FFF3E0; color: #E65100; }
    .badge-agendas { background: #FFF8E1; color: #F57F17; }
    .badge-campha { background: #E8F5E9; color: #2E7D32; }
    .badge-sin { background: #FFEBEE; color: #C62828; }
</style>
""", unsafe_allow_html=True)

CAMP_BADGE = {"Turnos": "badge-turnos", "Conmutador": "badge-conmutador",
              "Plan Médico": "badge-plan", "Portal": "badge-portal",
              "Agendas": "badge-agendas", "Camp HA": "badge-campha",
              "Sin asignar": "badge-sin"}

st.markdown("""
<div class="main-header">
    <h1>📊 AI Report Builder</h1>
    <p>Hospital Alemán · Productividad del Contact Center</p>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    st.selectbox("Tipo de reporte", ["Productividad del Contact Center"])
    st.divider()
    st.markdown("### 📋 Instrucciones")
    st.markdown(
        "1. Subí los **CSVs del mes actual**\n"
        "2. *(Opcional)* Subí también los del **mes anterior**\n"
        "3. **Seleccioná** las habilidades a incluir\n"
        "4. Revisá los KPIs\n"
        "5. Descargá el PPTX"
    )
    st.divider()
    st.caption("v1.3 · Selección + anexos + prom. correcto")

# ======================================================================
# Step 1: Upload
# ======================================================================
st.markdown('<h3 class="step-header">1 · Subir archivos CSV</h3>', unsafe_allow_html=True)

col_cur, col_prev = st.columns(2)
with col_cur:
    st.markdown("**📁 Mes actual** (obligatorio)")
    current_files = st.file_uploader("CSVs del mes a reportar", type=["csv"],
                                      accept_multiple_files=True, key="current")
with col_prev:
    st.markdown("**📁 Mes anterior** (opcional, para variaciones)")
    previous_files = st.file_uploader("CSVs del mes anterior", type=["csv"],
                                       accept_multiple_files=True, key="previous")

st.markdown("**📞 Llamadas salientes** (opcional, archivo aparte)")
outbound_file = st.file_uploader("CSV de llamadas salientes", type=["csv"],
                                  accept_multiple_files=False, key="outbound")

if not current_files:
    st.info("👆 Subí los archivos CSV del mes que querés reportar.")
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
    return dfs, period_label or "Período desconocido"


all_current_dfs, current_period = load_file_set(current_files)
prev_dfs, prev_period = (({}, None) if not previous_files else load_file_set(previous_files))

# ======================================================================
# Step 2: Skill selection
# ======================================================================
st.markdown('<h3 class="step-header">2 · Seleccionar habilidades a incluir</h3>', unsafe_allow_html=True)

# Init session state for selections
if "skill_selection" not in st.session_state:
    st.session_state.skill_selection = {}

# Reset selection if file list changes
all_skills = list(all_current_dfs.keys())
skills_key = tuple(sorted(all_skills))
if st.session_state.get("_skills_key") != skills_key:
    st.session_state.skill_selection = {s: True for s in all_skills}
    st.session_state._skills_key = skills_key

# Bulk action buttons
col_all, col_none, col_info = st.columns([1, 1, 3])
with col_all:
    if st.button("✅ Seleccionar todas", use_container_width=True):
        for s in all_skills:
            st.session_state.skill_selection[s] = True
        st.rerun()
with col_none:
    if st.button("❌ Deseleccionar todas", use_container_width=True):
        for s in all_skills:
            st.session_state.skill_selection[s] = False
        st.rerun()
with col_info:
    n_selected = sum(1 for v in st.session_state.skill_selection.values() if v)
    st.markdown(f"**{n_selected} de {len(all_skills)}** habilidades seleccionadas")

# Group skills by campaign for the checkboxes
# Build classification using find_campaign directly (no fake filenames)
classification_all = {}
for skill in all_skills:
    camp = find_campaign(skill)
    classification_all.setdefault(camp, []).append({"skill": skill})

for camp_name in CAMPAIGN_ORDER + ["Camp HA", "Sin asignar"]:
    if camp_name not in classification_all:
        continue
    skills = classification_all[camp_name]
    badge_class = CAMP_BADGE.get(camp_name, "badge-sin")
    st.markdown(f'<span class="camp-badge {badge_class}">{camp_name}</span>',
                unsafe_allow_html=True)

    cols = st.columns(4)
    for i, s in enumerate(skills):
        skill_name = s["skill"]
        with cols[i % 4]:
            st.session_state.skill_selection[skill_name] = st.checkbox(
                skill_name,
                value=st.session_state.skill_selection.get(skill_name, True),
                key=f"chk_{skill_name}",
            )

# Filter dataframes based on selection
current_dfs = {s: df for s, df in all_current_dfs.items()
               if st.session_state.skill_selection.get(s, False)}

if not current_dfs:
    st.warning("⚠️ No hay habilidades seleccionadas. Marcá al menos una para generar el reporte.")
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
global_variations = {}
if prev_dfs:
    prev_selected = {s: df for s, df in prev_dfs.items() if s in current_dfs}
    if prev_selected:
        all_prev = pd.concat([df.assign(_skill=n) for n, df in prev_selected.items()],
                              ignore_index=True)
        prev_kpis = compute_kpis(all_prev, kpi_defs)
        global_variations = compute_variation(global_kpis, prev_kpis)

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
        prev_skills = [s for s in skills if s in prev_dfs]
        if prev_skills:
            prev_camp_df = pd.concat([prev_dfs[s] for s in prev_skills], ignore_index=True)
            prev_camp_kpis = compute_kpis(prev_camp_df, kpi_defs)
            campaign_variations[camp_name] = compute_variation(campaign_kpis[camp_name],
                                                                 prev_camp_kpis)

skill_kpis = {n: compute_kpis(df, kpi_defs) for n, df in current_dfs.items()}

# ======================================================================
# Step 3: KPIs
# ======================================================================
st.markdown('<h3 class="step-header">3 · Indicadores</h3>', unsafe_allow_html=True)

def render_kpi_card(label, value, color, variation=None):
    var_html = ""
    if variation and variation.get("formatted", "—") != "—":
        css = "kpi-var-up" if variation["direction"] == "up" else "kpi-var-down"
        var_html = f'<div class="{css}">{variation["formatted"]}</div>'
    return (f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="color:{color}">{value}</div>{var_html}</div>')

st.markdown(f"#### Todas las campañas seleccionadas — {current_period}"
            + (f" vs {prev_period}" if prev_dfs else ""))

# Row 1: 2 big cards
cols_top = st.columns(2)
with cols_top[0]:
    st.markdown(render_kpi_card("Recibidas", global_kpis["recibidas"]["formatted"],
                                 "#1B3A5C", global_variations.get("recibidas")),
                unsafe_allow_html=True)
with cols_top[1]:
    st.markdown(render_kpi_card("Atendidas", global_kpis["atendidas"]["formatted"],
                                 "#5B9BD5", global_variations.get("atendidas")),
                unsafe_allow_html=True)

# Row 2: 3 cards
cols_bot = st.columns(3)
with cols_bot[0]:
    st.markdown(render_kpi_card("Prom. Diario Recibidas",
                                 global_kpis["promedio_recibidas"]["formatted"],
                                 "#7F8C8D"), unsafe_allow_html=True)
with cols_bot[1]:
    st.markdown(render_kpi_card("Prom. Diario Atendidas",
                                 global_kpis["promedio_atendidas"]["formatted"],
                                 "#7F8C8D"), unsafe_allow_html=True)
with cols_bot[2]:
    st.markdown(render_kpi_card("Nivel de Atención",
                                 global_kpis["nivel_atencion"]["formatted"],
                                 "#4CAF50", global_variations.get("nivel_atencion")),
                unsafe_allow_html=True)

# Time cards
st.markdown("")
time_cols = st.columns(3)
for col, kid, lab in zip(time_cols,
    ["tiempo_conversacion", "tiempo_demora", "tiempo_abandono"],
    ["Conversación", "Demora", "Abandono"]):
    with col:
        st.markdown(render_kpi_card(lab, global_kpis[kid]["formatted"], "#1B3A5C"),
                    unsafe_allow_html=True)

# Campaign KPIs
with st.expander("📊 KPIs por campaña" + (" (con variaciones)" if prev_dfs else ""), expanded=True):
    for camp_name in CAMPAIGN_ORDER + ["Camp HA"]:
        if camp_name not in campaign_kpis:
            continue
        ck = campaign_kpis[camp_name]
        cv = campaign_variations.get(camp_name, {})
        parts = [f"**{camp_name}** —"]
        for kid, lab in [("recibidas", "Rec"), ("atendidas", "At"), ("nivel_atencion", "NA")]:
            val = ck[kid]["formatted"]
            vr = cv.get(kid, {}).get("formatted", "")
            arrow = ""
            if vr and "▲" in vr: arrow = "🟢"
            elif vr and "▼" in vr: arrow = "🔴"
            parts.append(f"{lab}: **{val}**{' ' + arrow + ' ' + vr if vr else ''}")
        st.markdown(" · ".join(parts))

with st.expander("📋 Detalle por habilidad", expanded=False):
    rows = []
    for name in sorted(current_dfs.keys(), key=lambda n: -skill_kpis[n]["recibidas"]["value"]):
        sk = skill_kpis[name]
        rows.append({
            "Habilidad": name, "Campaña": find_campaign(name),
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
st.markdown('<h3 class="step-header">4 · Generar reporte</h3>', unsafe_allow_html=True)

chart_dir = Path(tempfile.mkdtemp())
chart_images = {}

# Daily by campaign (aggregated)
daily_by_campaign = {}
for camp_name, camp_df in campaign_dfs.items():
    daily = aggregate_daily(camp_df)
    if len(daily) > 0:
        daily_by_campaign[camp_name] = daily
        key = f"daily_{camp_name.lower().replace(' ', '_').replace('é', 'e')}"
        fig = chart_daily_distribution(daily, title=f"Distribución diaria — {camp_name}")
        chart_images[key] = str(save_chart(fig, chart_dir / f"{key}.png"))
        plt.close(fig)

# All (aggregated across campaigns)
daily_all = aggregate_daily(all_current)
if len(daily_all) > 0:
    fig = chart_daily_distribution(daily_all,
                                    title="Distribución diaria — Todas las campañas")
    chart_images["daily_all"] = str(save_chart(fig, chart_dir / "daily_all.png"))
    plt.close(fig)

# All no Gipfel
daily_ng = aggregate_daily(all_no_gipfel)
if len(daily_ng) > 0:
    fig = chart_daily_distribution(daily_ng,
                                    title="Distribución diaria — Todas las campañas (sin Gipfel)")
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
        ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"],
        wk["rec"].tolist(), wk["att"].tolist(), wk["na"].tolist(),
        title="Distribución por día de semana")
    chart_images["weekday_distribution"] = str(save_chart(fig, chart_dir / "weekday.png"))
    plt.close(fig)

# Campaign volume + share
camp_sorted = [c for c in CAMPAIGN_ORDER + ["Camp HA"] if c in campaign_kpis]
if camp_sorted:
    rec = [campaign_kpis[c]["recibidas"]["value"] for c in camp_sorted]
    att = [campaign_kpis[c]["atendidas"]["value"] for c in camp_sorted]
    # Horizontal bars include ALL campaigns (Agendas, Camp HA too)
    fig = chart_horizontal_bars(camp_sorted, rec, att, title="Distribución por campaña")
    chart_images["campaign_volume"] = str(save_chart(fig, chart_dir / "camp_vol.png"))
    plt.close(fig)

    # Donut EXCLUDES Agendas and Camp HA (too small; matches original report).
    # Center total = sum of the slices actually shown in the donut.
    donut_campaigns = [c for c in camp_sorted if c not in ("Agendas", "Camp HA")]
    donut_rec = [campaign_kpis[c]["recibidas"]["value"] for c in donut_campaigns]
    donut_total = int(sum(donut_rec))
    total_str = f"{donut_total:,}".replace(",", ".")
    fig = chart_donut(donut_campaigns, donut_rec, title="Participación por campaña",
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

# ---- Monthly trend (evolución mensual) ----
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
    # Build trend up to current month
    trend_records = get_trend(cur_year, cur_month)
    monthly_trend_data = [
        {"month_name": r.month_name, "recibidas": r.recibidas,
         "atendidas": r.atendidas, "nivel_atencion": r.nivel_atencion}
        for r in trend_records
    ]
    if len(monthly_trend_data) >= 2:
        fig = chart_grouped_bar_line(
            [r["month_name"] for r in monthly_trend_data],
            [r["recibidas"] for r in monthly_trend_data],
            [r["atendidas"] for r in monthly_trend_data],
            [r["nivel_atencion"] for r in monthly_trend_data],
            title=f"Evolución mensual {cur_year}",
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
            fig = chart_vertical_bars(results, counts, title="Distribución por resultado")
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
                                      title="Distribución diaria — Llamadas salientes")
            chart_images["outbound_daily"] = str(save_chart(fig, chart_dir / "ob_daily.png"))
            plt.close(fig)

        st.success(f"📞 Llamadas salientes cargadas: {ob_agg['total']:,} llamadas".replace(",", "."))
    except Exception as e:
        st.error(f"Error al procesar llamadas salientes: {e}")

# Preview
with st.expander("👁️ Vista previa de gráficos", expanded=False):
    if "daily_all" in chart_images:
        st.image(chart_images["daily_all"], caption="Distribución diaria — Todas las campañas")
    for camp_name in CAMPAIGN_ORDER:
        key = f"daily_{camp_name.lower().replace(' ', '_').replace('é', 'e')}"
        if key in chart_images:
            st.image(chart_images[key], caption=f"Distribución diaria — {camp_name}")

# ======================================================================
# Generate PPTX
# ======================================================================
generate_btn = st.button("🚀 Generar reporte PPTX", type="primary", use_container_width=True)

if generate_btn:
    with st.spinner("Generando reporte..."):
        fmt = lambda kpis: {k: v["formatted"] for k, v in kpis.items()}
        fmt_var = lambda vars: {k: v.get("formatted", "") for k, v in vars.items()} if vars else {}

        pptx_campaigns = []
        pptx_campaigns.append({
            "name": "Todas las Campañas", "is_all": True,
            "kpis": fmt(global_kpis),
            "variations": fmt_var(global_variations),
            "chart_path": chart_images.get("daily_all", ""),
        })
        if global_ng_kpis:
            pptx_campaigns.append({
                "name": "Todas las Campañas (sin Gipfel)", "is_all": True,
                "kpis": fmt(global_ng_kpis), "variations": {},
                "chart_path": chart_images.get("daily_all_no_gipfel", ""),
            })
        for camp_name in CAMPAIGN_ORDER:
            if camp_name not in campaign_kpis:
                continue
            key = f"daily_{camp_name.lower().replace(' ', '_').replace('é', 'e')}"
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
        )

    st.success(f"✅ Reporte generado exitosamente ({len(pptx_campaigns)} campañas, {len(annexes)} anexos)")
    slug = current_period.replace(" ", "_")
    st.download_button(
        label="📥 Descargar reporte PPTX",
        data=pptx_bytes,
        file_name=f"Reporte_CCenter_{slug}.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        type="primary", use_container_width=True,
    )
