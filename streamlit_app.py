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
    chart_vertical_bars, chart_outbound_results, chart_outbound_daily,
    save_chart,
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
                          card as ha_card, chip as ha_chip,
                          table as ha_table, _render as ha_render)

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
_scope_label = None

# Version banner \u2014 lets you confirm at a glance which version is deployed
APP_VERSION = "4.0.2"
st.caption(f"Versi\u00f3n {APP_VERSION} \u00b7 Contact Center y Plan M\u00e9dico \u00b7 hist\u00f3rico en archivo")

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
    st.caption(f"v{APP_VERSION} \u00b7 Asistente por pasos")

# ======================================================================
# Wizard state
#
# One step at a time. Widgets are only rendered on their own step, so
# anything that must survive is copied into plain (non-widget) keys, which
# Streamlit does not garbage-collect.
# ======================================================================
PASOS = ["Subir archivos", "Elegir alcance", "Revisar indicadores", "Generar reporte"]
_paso = st.session_state.setdefault("paso", 1)


def _ir_a(n: int) -> None:
    st.session_state.paso = n


def _barra_progreso(actual: int) -> None:
    tramos = "".join(
        f'<div style="flex:1;height:5px;border-radius:3px;background:'
        f'{"#0B6E63" if i < actual else "#E4E9E8"}"></div>'
        for i in range(1, len(PASOS) + 1))
    ha_render(
        f'<div style="display:flex;gap:.45rem;margin:1.4rem 0 .7rem">{tramos}</div>'
        f'<div style="font:600 .72rem Inter,sans-serif;letter-spacing:.09em;'
        f'text-transform:uppercase;color:#0B6E63">Paso {actual} de {len(PASOS)}</div>'
        f'<h2 style="font-family:Outfit,Inter,sans-serif;font-size:1.35rem;'
        f'font-weight:600;margin:.15rem 0 1.1rem">{PASOS[actual - 1]}</h2>')


_barra_progreso(_paso)

# ======================================================================
# Step 1: Upload
# ======================================================================
if _paso == 1:

    col_cur, col_prev = st.columns(2)
    with col_cur:
        st.markdown("**Mes actual** \u00b7 obligatorio")
        st.file_uploader("CSVs del mes a reportar", type=["csv"],
                         accept_multiple_files=True, key="current")
    with col_prev:
        st.markdown("**Mes anterior** \u00b7 opcional, para comparar")
        st.file_uploader("CSVs del mes anterior", type=["csv"],
                         accept_multiple_files=True, key="previous")

    st.markdown("**Llamadas salientes** \u00b7 opcional, archivo aparte")
    st.file_uploader("CSV de llamadas salientes", type=["csv"],
                     accept_multiple_files=False, key="outbound")

    st.markdown("**Hist\u00f3rico de meses anteriores** \u00b7 recomendado")
    st.caption("El archivo que descargaste la vez anterior. Sirve para el gr\u00e1fico de "
               "evoluci\u00f3n mensual: sin \u00e9l, el servidor puede haber perdido los meses previos.")
    st.file_uploader("CSV de hist\u00f3rico", type=["csv"],
                     accept_multiple_files=False, key="history")

    # Coming back to step 1 re-renders the uploaders empty, because Streamlit
    # drops the state of widgets that were off screen. The parsed data is
    # still cached, so the already-loaded files are shown and reused instead
    # of forcing the user to pick them again.
    _cur = st.session_state.get("current") or []
    _cache = st.session_state.get("archivos")
    _nombres_now = [f.name for f in _cur]

    if _cur and _nombres_now != (_cache or {}).get("nombres"):
        st.session_state.pop("archivos", None)          # a new upload replaces it
        _cache = None

    st.markdown("")
    if not _cur and _cache:
        st.success(f"Ya ten\u00e9s cargados {len(_cache['current'])} archivo(s) de "
                   f"{_cache['current_period']}. Pod\u00e9s continuar, o subir otros "
                   f"para reemplazarlos.")
    elif not _cur:
        st.info("Sub\u00ed al menos los CSV del mes que quer\u00e9s reportar.")

    _puede = bool(_cur) or bool(_cache)
    _c1, _c2 = st.columns([3, 1])
    with _c2:
        if st.button("Continuar", type="primary", use_container_width=True,
                     disabled=not _puede):
            st.session_state.pop("seleccion", None)
            st.session_state.pop("reporte", None)
            _ir_a(2)
            st.rerun()
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


# The uploaders only exist on step 1, so the parsed data is cached here and
# reused from step 2 onwards.
current_files = st.session_state.get("current") or []
previous_files = st.session_state.get("previous") or []
outbound_file = st.session_state.get("outbound")
history_file = st.session_state.get("history")

if "archivos" not in st.session_state:
    with st.spinner("Leyendo los archivos..."):
        _cur_dfs, _cur_per = load_file_set(current_files)
        _prev_dfs, _prev_per = (({}, None) if not previous_files
                                else load_file_set(previous_files))
    # The uploaders live on step 1 only, so their CONTENT is cached too --
    # otherwise the outbound and history files disappear on later steps and
    # their report pages were silently skipped.
    _ob = None
    if outbound_file is not None:
        outbound_file.seek(0)
        _ob = {"nombre": outbound_file.name, "bytes": outbound_file.read()}
    _hi = None
    if history_file is not None:
        history_file.seek(0)
        _hi = history_file.read()

    st.session_state["archivos"] = {
        "current": _cur_dfs, "current_period": _cur_per,
        "prev": _prev_dfs, "prev_period": _prev_per,
        "nombres": [f.name for f in current_files],
        "nombres_prev": [f.name for f in previous_files],
        "outbound": _ob,
        "historico": _hi,
        "historico_aplicado": False,
    }

_arch = st.session_state["archivos"]
all_current_dfs = _arch["current"]
current_period = _arch["current_period"]
prev_dfs = _arch["prev"]
prev_period = _arch["prev_period"]
_nombres_actual = _arch.get("nombres", [])
_outbound_cache = _arch.get("outbound")
_historico_cache = _arch.get("historico")

if not all_current_dfs:
    st.error("No pude leer ninguna habilidad de los archivos cargados.")
    if st.button("Volver a subir archivos"):
        st.session_state.pop("archivos", None)
        _ir_a(1); st.rerun()
    st.stop()

# ======================================================================
# Step 2: Skill selection
# ======================================================================
if _paso == 2:

    # ---------------------------------------------------------------
    # Selection state
    #
    # The checkbox keys ("chk_<skill>") ARE the state. Streamlit forbids writing
    # a widget's key after the widget has been created, and ignores `value=` once
    # the key exists -- which is why changing a separate dict did nothing. Every
    # change therefore happens inside a callback, which runs before the widgets
    # are rebuilt on the next run.
    # ---------------------------------------------------------------
    all_skills = sorted(set(all_current_dfs) | set(prev_dfs))
    skills_key = tuple(all_skills)

    if st.session_state.get("_skills_key") != skills_key:
        for _k in [k for k in st.session_state if k.startswith("chk_")]:
            del st.session_state[_k]
        st.session_state._skills_key = skills_key
        st.session_state.pop("scope_mode", None)

    for _sk in all_skills:
        st.session_state.setdefault(f"chk_{_sk}", True)


    def _set_all(value: bool) -> None:
        for sk in all_skills:
            st.session_state[f"chk_{sk}"] = value


    def _apply_scope() -> None:
        """Tick exactly the skills the chosen scope covers.

        The callback runs BEFORE the campaign/skill selectbox is created, so on
        the run where the scope changes its key does not exist yet. Falling back
        to the first option keeps it in step with what the selectbox will show.
        """
        modo = st.session_state.get("scope_mode", "Todo el Contact Center")
        campanas = sorted({find_campaign(sk) for sk in all_skills} - {"Sin asignar"})

        if modo == "Una campana":
            camp = st.session_state.get("scope_camp")
            if camp not in campanas:
                camp = campanas[0] if campanas else None
            objetivo = {sk for sk in all_skills if find_campaign(sk) == camp}
        elif modo == "Una habilidad":
            elegida = st.session_state.get("scope_skill")
            if elegida not in all_skills:
                elegida = sorted(all_skills)[0] if all_skills else None
            objetivo = {elegida} if elegida else set()
        else:
            objetivo = set(all_skills)

        for sk in all_skills:
            st.session_state[f"chk_{sk}"] = sk in objetivo


    _campanas = sorted({find_campaign(sk) for sk in all_skills} - {"Sin asignar"})

    st.markdown("**Alcance**")
    _alcance = st.radio(
        "Alcance del reporte", ["Todo el Contact Center", "Una campana", "Una habilidad"],
        horizontal=True, key="scope_mode", on_change=_apply_scope,
        label_visibility="collapsed",
        help="Para armar un reporte enfocado, por ejemplo solo Turnos o solo la "
             "habilidad PM Consultas.",
    )

    _foco = None
    if _alcance == "Una campana" and _campanas:
        _foco = st.selectbox("Campana", _campanas, key="scope_camp",
                             on_change=_apply_scope)
    elif _alcance == "Una habilidad" and all_skills:
        _foco = st.selectbox("Habilidad", sorted(all_skills), key="scope_skill",
                             on_change=_apply_scope)

    st.markdown("")
    col_all, col_none, col_info = st.columns([1, 1, 3])
    with col_all:
        st.button("Seleccionar todas", use_container_width=True,
                  on_click=_set_all, args=(True,))
    with col_none:
        st.button("Deseleccionar todas", use_container_width=True,
                  on_click=_set_all, args=(False,))
    with col_info:
        n_selected = sum(1 for s in all_skills if st.session_state.get(f"chk_{s}"))
        st.markdown(f"**{n_selected} de {len(all_skills)}** habilidades seleccionadas")

    if prev_dfs:
        st.caption("Lo que destildes se excluye del reporte Y de la comparacion "
                   "con el mes anterior.")

    # When a skill shows up as "solo <mes>" the usual cause is that the two
    # files produced different skill names. This makes that visible instead
    # of leaving the user guessing.
    _solo_uno = [sk for sk in all_skills
                 if (sk in all_current_dfs) != (sk in prev_dfs)]
    if prev_dfs and _solo_uno:
        with st.expander(f"Por que {len(_solo_uno)} habilidad(es) figuran en un solo mes"):
            st.caption("Nombre de archivo \u2192 habilidad detectada. Si el mismo "
                       "dato aparece con dos nombres distintos, renombra uno de los "
                       "archivos para que coincidan.")
            _filas = []
            for _n in _arch.get("nombres", []):
                _filas.append({"Archivo": _n, "Mes": current_period,
                               "Habilidad detectada": extract_skill_name(_n)})
            for _n in _arch.get("nombres_prev", []):
                _filas.append({"Archivo": _n, "Mes": prev_period or "anterior",
                               "Habilidad detectada": extract_skill_name(_n)})
            _filas.sort(key=lambda r: (r["Habilidad detectada"].lower(), r["Mes"]))
            ha_table(_filas)

    classification_all = {}
    for skill in all_skills:
        classification_all.setdefault(find_campaign(skill), []).append(skill)

    for camp_name in CAMPAIGN_ORDER + ["Camp HA", "Sin asignar"]:
        if camp_name not in classification_all:
            continue
        ha_render(ha_chip(camp_name, muted=(camp_name == "Sin asignar")))
        cols = st.columns(4)
        for i, skill_name in enumerate(classification_all[camp_name]):
            label = skill_name
            if prev_dfs:
                in_cur = skill_name in all_current_dfs
                in_prev = skill_name in prev_dfs
                if in_cur and not in_prev:
                    label = f"{skill_name}  (solo {current_period})"
                elif in_prev and not in_cur:
                    label = f"{skill_name}  (solo {prev_period})"
            with cols[i % 4]:
                # No `value=`: the key alone holds the state.
                st.checkbox(label, key=f"chk_{skill_name}")

    st.markdown("")
    _b1, _b2, _b3 = st.columns([1, 2, 1])
    with _b1:
        if st.button("Volver", use_container_width=True):
            _ir_a(1); st.rerun()
    with _b3:
        _sel_now = [k for k in all_skills if st.session_state.get(f"chk_{k}")]
        if st.button("Continuar", type="primary", use_container_width=True,
                     disabled=not _sel_now):
            st.session_state["seleccion"] = _sel_now
            st.session_state["foco"] = _foco
            st.session_state.pop("reporte", None)
            _ir_a(3); st.rerun()
    if not [k for k in all_skills if st.session_state.get(f"chk_{k}")]:
        st.info("Marca al menos una habilidad para continuar.")
    st.stop()

# From step 3 onwards the checkboxes are not on screen, so the stored list is
# what defines the selection.
_seleccion = st.session_state.get("seleccion", list(all_current_dfs))
_foco = st.session_state.get("foco")

# Apply the selection to BOTH months
current_dfs = {s: df for s, df in all_current_dfs.items() if s in _seleccion}
prev_dfs = {s: df for s, df in prev_dfs.items() if s in _seleccion}

if not current_dfs:
    st.warning("No hay habilidades seleccionadas.")
    if st.button("Volver a elegir"):
        _ir_a(2); st.rerun()
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
# Helpers shared by steps 3 and 4
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
# Step 3: KPIs
# ======================================================================
if _paso == 3:

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
        ha_table(rows)

    # ======================================================================
    # Aggregate helpers
    # ======================================================================
    st.markdown("")
    _b1, _b2, _b3 = st.columns([1, 2, 1])
    with _b1:
        if st.button("Volver", use_container_width=True):
            _ir_a(2); st.rerun()
    with _b3:
        if st.button("Continuar", type="primary", use_container_width=True):
            _ir_a(4); st.rerun()
    st.stop()

# ======================================================================
# Step 4: Charts
# ======================================================================
_nb1, _nb2 = st.columns([1, 4])
with _nb1:
    if st.button("Volver", use_container_width=True):
        _ir_a(3); st.rerun()

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
# With a single campaign there is nothing to compare, so the volume and
# share charts are skipped rather than drawn with one bar / one slice.
if len(camp_sorted) > 1:
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
from app.data_loader.monthly_history import (get_trend, add_month,
                                              export_history_csv,
                                              import_history_csv,
                                              missing_months)

# Load the uploaded history first, so the trend is complete before the
# current month is added to it.
# Re-imported on every run rather than once: the server can restart and wipe
# the stored file at any moment, and a one-shot import would leave the trend
# silently incomplete. Importing again is cheap and idempotent.
if _historico_cache is not None:
    try:
        _n, _warn = import_history_csv(
            _historico_cache.decode("utf-8-sig", errors="replace"))
        if _n and not _arch.get("historico_avisado"):
            st.success(f"Hist\u00f3rico cargado: {_n} mes(es).")
            _arch["historico_avisado"] = True
        for _w in _warn:
            st.warning(_w)
    except Exception as _e:
        st.error(f"No pude leer el hist\u00f3rico: {_e}")
from app.data_loader.skill_mapper import extract_period as _extract_period_full

# Determine current month/year from the period label
_period_info = None
for _nombre in _nombres_actual:
    _period_info = _extract_period_full(_nombre)
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
    # A gap means that month was never reported, or it was lost when the
    # server restarted. Uploading the history file is what prevents this.
    _faltan = missing_months(cur_year, cur_month)
    if _faltan:
        if history_file is None:
            st.warning(
                "Faltan meses en la evoluci\u00f3n mensual: " + ", ".join(_faltan) +
                ". Sub\u00ed el archivo de hist\u00f3rico en el paso 1 (el que descargaste "
                "la vez anterior) y vuelven a aparecer.")
        else:
            st.info(
                "Faltan meses en la evoluci\u00f3n mensual: " + ", ".join(_faltan) +
                ". El hist\u00f3rico que subiste no los incluye. Se completan generando "
                "una vez el reporte de ese mes, o agregando la fila a mano en el CSV.")

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
if _outbound_cache is not None:
    from app.data_loader.outbound_loader import (
        load_outbound_csv, aggregate_outbound, count_rotaciones_am,
    )
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        tmp.write(_outbound_cache["bytes"]); tmp.close()
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
            fig = chart_outbound_results(results, counts,
                                          title="Distribuci\u00f3n por resultado")
            chart_images["outbound_result"] = str(save_chart(fig, chart_dir / "ob_result.png"))
            plt.close(fig)

        # Chart: daily distribution
        if len(ob_agg["daily"]) > 0:
            daily_ob = ob_agg["daily"]
            month_names = {1:"ene",2:"feb",3:"mar",4:"abr",5:"may",6:"jun",
                           7:"jul",8:"ago",9:"sep",10:"oct",11:"nov",12:"dic"}
            labels = [f"{pd.Timestamp(d).day}-{month_names.get(pd.Timestamp(d).month,'?')}"
                      for d in daily_ob["date"]]
            fig = chart_outbound_daily(labels, daily_ob["count"].tolist(),
                                       title="Distribuci\u00f3n diaria \u2014 Llamadas salientes")
            chart_images["outbound_daily"] = str(save_chart(fig, chart_dir / "ob_daily.png"))
            plt.close(fig)

        st.success(f"Llamadas salientes cargadas: {ob_agg['total']:,} llamadas".replace(",", "."))
    except Exception as e:
        st.error(f"Error al procesar llamadas salientes: {e}")

# ---- Resumen ejecutivo y conclusiones ----
# Built from the report's own figures: free, instant, nothing leaves the app
# and no number can be invented.
from app.ai_engine.summary_builder import build_executive_summary, build_conclusions

ai_texts = {}
with st.expander("Resumen ejecutivo y conclusiones", expanded=True):
    st.caption("Se arman con los numeros del propio reporte. Podes editarlos "
               "antes de generar el PPTX.")

    _resumen = build_executive_summary(
        current_period, global_kpis, global_variations, campaign_kpis, prev_period)
    _conclusiones = build_conclusions(
        current_period, global_kpis, global_variations, campaign_kpis, skill_kpis)

    st.markdown("**Resumen ejecutivo**")
    ai_texts["resumen"] = st.text_area("resumen", _resumen, height=130,
                                        label_visibility="collapsed")
    st.markdown("**Conclusiones**")
    ai_texts["conclusiones"] = st.text_area("conclusiones", _conclusiones, height=180,
                                             label_visibility="collapsed")

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

    # A download_button reruns the script, and st.button() is False on that
    # run, so anything rendered inside "if generate_btn" would vanish and the
    # report had to be generated again. Storing the result keeps all three
    # downloads available until a new report is generated.
    slug = current_period.replace(" ", "_")
    if _foco:
        _clean = "".join(ch if ch.isalnum() else "_" for ch in _foco).strip("_")
        slug = f"{_clean}_{slug}"

    st.session_state["reporte"] = {
        "pptx": pptx_bytes,
        "pdf": pdf_bytes,
        "historico": export_history_csv().encode("utf-8-sig"),
        "slug": slug,
        "periodo": current_period,
        "foco": _foco,
        "secciones": len(pptx_campaigns),
        "anexos": len(annexes),
    }

# ---- Descargas ----
# Rendered outside the generate block, from the stored result.
_rep = st.session_state.get("reporte")
if _rep:
    _que = f"{_rep['foco']} \u00b7 " if _rep.get("foco") else ""
    st.success(f"Reporte de {_rep['periodo']} listo \u00b7 {_que}"
               f"{_rep['secciones']} secci\u00f3n(es), {_rep['anexos']} anexo(s)")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Descargar PPTX", data=_rep["pptx"],
            file_name=f"Reporte_CCenter_{_rep['slug']}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            type="primary", use_container_width=True, key="dl_pptx")
    with c2:
        st.download_button(
            "Descargar PDF", data=_rep["pdf"],
            file_name=f"Reporte_CCenter_{_rep['slug']}.pdf",
            mime="application/pdf", use_container_width=True, key="dl_pdf")

    st.download_button(
        "Descargar hist\u00f3rico actualizado", data=_rep["historico"],
        file_name="historico_contact_center.csv", mime="text/csv",
        use_container_width=True, key="dl_hist")
    st.caption("Los tres archivos siguen disponibles: pod\u00e9s bajarlos en "
               "cualquier orden sin volver a generar el reporte. "
               "Guard\u00e1 el hist\u00f3rico en la carpeta compartida pisando el anterior.")

    st.markdown("")
    if st.button("Hacer otro reporte", use_container_width=True):
        for _k in ("archivos", "seleccion", "reporte", "current", "previous",
                   "outbound", "history", "_skills_key"):
            st.session_state.pop(_k, None)
        for _k in [k for k in list(st.session_state) if k.startswith("chk_")]:
            del st.session_state[_k]
        _ir_a(1)
        st.rerun()
