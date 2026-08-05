"""Generate test charts from the real PM_Consultas CSV to verify visual output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chart_engine.renderer import (
    chart_daily_distribution,
    chart_donut,
    chart_grouped_bar_line,
    chart_horizontal_bars,
    chart_vertical_bars,
    save_chart,
)
from app.data_loader.csv_loader import load_csv
from app.plugins.contact_center.plugin import ContactCenterPlugin

OUTPUT_DIR = Path("/home/claude/ai-report-builder/test_output")
OUTPUT_DIR.mkdir(exist_ok=True)

plugin = ContactCenterPlugin()
schema = plugin.get_schema()

df = load_csv(Path("/mnt/user-data/uploads/PM_Consultas_may26.csv"), schema=schema)

print(f"Loaded {len(df)} rows from PM_Consultas_may26.csv")

# 1. Daily distribution
fig = chart_daily_distribution(df, title="Distribuci\u00f3n diaria \u2014 PM Consultas")
save_chart(fig, OUTPUT_DIR / "01_daily_distribution.png")
print("\u2713 01_daily_distribution.png")

# 2. Weekday distribution (aggregate by day of week)
df["weekday"] = df["date"].dt.dayofweek  # 0=Mon ... 6=Sun
weekday_agg = df.groupby("weekday").agg(
    recibidas=("TOTALCALLS", "sum"),
    atendidas=("TRANSFER", "sum"),
).reset_index()
weekday_agg["na"] = (weekday_agg["atendidas"] / weekday_agg["recibidas"] * 100).round(2)
day_labels = ["lun", "mar", "mi\u00e9", "jue", "vie", "s\u00e1b", "dom"]
# Reindex to include all days
weekday_full = weekday_agg.set_index("weekday").reindex(range(7), fill_value=0).reset_index()

fig = chart_grouped_bar_line(
    labels=day_labels,
    recibidas=weekday_full["recibidas"].tolist(),
    atendidas=weekday_full["atendidas"].tolist(),
    nivel_atencion=weekday_full["na"].replace(0, float("nan")).tolist(),
    title="Distribuci\u00f3n por d\u00eda de semana \u2014 PM Consultas",
)
save_chart(fig, OUTPUT_DIR / "02_weekday_distribution.png")
print("\u2713 02_weekday_distribution.png")

# 3. Horizontal bars (simulating campaign volumes)
campaigns = ["Turnos", "Conmutador", "Plan M\u00e9dico", "Portal", "Agendas", "Camp HA"]
rec = [38044, 27803, 8754, 2876, 51, 2]
att = [34076, 25944, 7169, 2506, 43, 2]

fig = chart_horizontal_bars(
    labels=campaigns,
    recibidas=rec,
    atendidas=att,
    title="Distribuci\u00f3n por campa\u00f1a",
)
save_chart(fig, OUTPUT_DIR / "03_campaign_volume.png")
print("\u2713 03_campaign_volume.png")

# 4. Donut (campaign share)
fig = chart_donut(
    labels=campaigns,
    values=rec,
    title="Participaci\u00f3n por campa\u00f1a",
    center_value="77.530",
    center_label="Total recibidas",
    threshold_pct=0.5,
)
save_chart(fig, OUTPUT_DIR / "04_campaign_share.png")
print("\u2713 04_campaign_share.png")

# 5. Monthly evolution (simulated Ene-May data from the report)
months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo"]
rec_m = [79134, 77037, 87251, 83699, 77530]
att_m = [73033, 67275, 80068, 73880, 69740]
na_m = [92.3, 87.3, 91.8, 88.3, 90.0]

fig = chart_grouped_bar_line(
    labels=months,
    recibidas=rec_m,
    atendidas=att_m,
    nivel_atencion=na_m,
    title="Evoluci\u00f3n mensual 2026",
    y_na_min=60.0,
)
save_chart(fig, OUTPUT_DIR / "05_monthly_evolution.png")
print("\u2713 05_monthly_evolution.png")

# 6. Outbound distribution (from report page 13)
result_labels = ["Conectado", "No llama\nCancelada por Asesor", "Ocupado", "No contesta\nCancelada Prediscado"]
result_values = [2112, 324, 245, 136]

fig = chart_vertical_bars(
    labels=result_labels,
    values=result_values,
    title="Distribuci\u00f3n por resultado",
)
save_chart(fig, OUTPUT_DIR / "06_outbound_result.png")
print("\u2713 06_outbound_result.png")

print(f"\nAll charts saved to {OUTPUT_DIR}/")
