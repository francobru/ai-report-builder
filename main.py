"""AI Report Builder \u2014 Main entry point.

Supports two modes:
  1. CLI mode (for testing):  python main.py --files *.csv --output report.pptx
  2. GUI mode (production):   python main.py  (launches PySide6 window)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.core.pipeline import PipelineContext, ReportPipeline
from app.core.plugin_registry import registry
from app.data_loader.csv_loader import load_csv, load_multiple_csvs
from app.data_loader.validator import validate
from app.kpi_engine.calculator import compute_kpis, compute_variation
from app.chart_engine.renderer import (
    chart_daily_distribution,
    chart_donut,
    chart_grouped_bar_line,
    chart_horizontal_bars,
    save_chart,
)


def _detect_period(ctx: PipelineContext) -> str:
    """Detect the period label from the loaded data."""
    import pandas as pd
    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }
    for _name, df in ctx.raw_dataframes.items():
        if "date" in df.columns:
            dates = df["date"].dropna()
            if not dates.empty:
                month = dates.iloc[0].month
                year = dates.iloc[0].year
                return f"{month_names.get(month, '?')} {year}"
    return "Per\u00edodo desconocido"


# ======================================================================
# Pipeline stages
# ======================================================================

def stage_load_data(ctx: PipelineContext) -> PipelineContext:
    """Stage 1: Load all CSV files."""
    schema = ctx.plugin.get_schema()
    ctx.raw_dataframes = load_multiple_csvs(ctx.input_files, schema=schema)
    print(f"  Loaded {len(ctx.raw_dataframes)} file(s)")
    return ctx


def stage_validate(ctx: PipelineContext) -> PipelineContext:
    """Stage 2: Validate all loaded data."""
    schema = ctx.plugin.get_schema()
    for name, df in ctx.raw_dataframes.items():
        result = validate(df, schema, source_name=name)
        if not result.is_valid:
            ctx.validation_errors.extend(result.errors)
        ctx.validation_warnings.extend(result.warnings)
        print(f"  {name}: {result.summary}")

    if ctx.validation_errors:
        print(f"  \u26a0 {len(ctx.validation_errors)} error(s) found")
    return ctx


def stage_combine_data(ctx: PipelineContext) -> PipelineContext:
    """Stage 3: Combine files and group by campaign."""
    import pandas as pd

    # Combine all into one master DataFrame
    all_dfs = []
    for name, df in ctx.raw_dataframes.items():
        df = df.copy()
        df["_skill_name"] = name
        all_dfs.append(df)

    if all_dfs:
        ctx.combined_data = pd.concat(all_dfs, ignore_index=True)
    else:
        ctx.combined_data = pd.DataFrame()

    # Group by campaign using plugin mapping
    mapping = ctx.plugin.get_campaign_mapping()
    for campaign_name, skill_stems in mapping.items():
        # Match skill stems case-insensitively
        skill_lower = [s.lower() for s in skill_stems]
        mask = ctx.combined_data["_skill_name"].str.lower().isin(skill_lower)
        campaign_df = ctx.combined_data[mask]
        if not campaign_df.empty:
            ctx.campaign_data[campaign_name] = campaign_df

    # Detect period
    ctx.period_label = _detect_period(ctx)
    print(f"  Period: {ctx.period_label}")
    print(f"  Campaigns found: {list(ctx.campaign_data.keys())}")
    return ctx


def stage_compute_kpis(ctx: PipelineContext) -> PipelineContext:
    """Stage 4: Compute KPIs for global and per-campaign."""
    kpi_defs = ctx.plugin.get_kpis()

    # Global KPIs (all data combined)
    if ctx.combined_data is not None and not ctx.combined_data.empty:
        ctx.kpi_results["global"] = compute_kpis(ctx.combined_data, kpi_defs)

    # Per-campaign KPIs
    for camp_name, camp_df in ctx.campaign_data.items():
        ctx.campaign_kpis[camp_name] = compute_kpis(camp_df, kpi_defs)

    # Per-skill KPIs (for the skills detail table)
    skill_table = []
    for name, df in ctx.raw_dataframes.items():
        sk_kpis = compute_kpis(df, kpi_defs)
        skill_table.append({
            "name": name,
            "recibidas": sk_kpis["recibidas"]["formatted"],
            "atendidas": sk_kpis["atendidas"]["formatted"],
            "na": sk_kpis["nivel_atencion"]["formatted"],
            "conversacion": sk_kpis["tiempo_conversacion"]["formatted"],
            "demora": sk_kpis["tiempo_demora"]["formatted"],
            "abandono": sk_kpis["tiempo_abandono"]["formatted"],
        })
    skill_table.sort(key=lambda s: float(
        s["recibidas"].replace(".", "").replace(",", ".")
    ), reverse=True)
    ctx.kpi_results["skill_table"] = skill_table

    print(f"  Computed KPIs for {len(ctx.campaign_kpis)} campaigns + global")
    return ctx


def stage_generate_charts(ctx: PipelineContext) -> PipelineContext:
    """Stage 5: Generate all charts as PNG images."""
    chart_dir = Path("output/charts")
    chart_dir.mkdir(parents=True, exist_ok=True)

    # Daily distribution per skill/campaign
    for name, df in ctx.raw_dataframes.items():
        if "date" not in df.columns:
            continue
        fig = chart_daily_distribution(df, title=f"Distribuci\u00f3n diaria \u2014 {name}")
        path = save_chart(fig, chart_dir / f"daily_{name}.png")
        ctx.chart_images[f"daily_{name}"] = path

    # Weekday distribution (all data)
    if ctx.combined_data is not None and "date" in ctx.combined_data.columns:
        import pandas as pd
        df_all = ctx.combined_data.copy()
        df_all["weekday"] = df_all["date"].dt.dayofweek
        wk = df_all.groupby("weekday").agg(
            rec=("TOTALCALLS", "sum"),
            att=("TRANSFER", "sum"),
        ).reindex(range(7), fill_value=0)
        wk["na"] = (wk["att"] / wk["rec"].replace(0, 1) * 100).round(2)

        day_labels = ["lun", "mar", "mi\u00e9", "jue", "vie", "s\u00e1b", "dom"]
        fig = chart_grouped_bar_line(
            labels=day_labels,
            recibidas=wk["rec"].tolist(),
            atendidas=wk["att"].tolist(),
            nivel_atencion=wk["na"].tolist(),
            title="Distribuci\u00f3n por d\u00eda de semana",
        )
        path = save_chart(fig, chart_dir / "weekday_distribution.png")
        ctx.chart_images["weekday_distribution"] = path

    print(f"  Generated {len(ctx.chart_images)} charts")
    return ctx


def stage_generate_report(ctx: PipelineContext) -> PipelineContext:
    """Stage 6: Assemble the final PPTX."""
    from app.report_generator.pptx_generator import generate_pptx

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    period_slug = ctx.period_label.replace(" ", "_")
    output_path = output_dir / f"Reporte_CCenter_{period_slug}.pptx"

    ctx.output_path = generate_pptx(ctx, output_path)
    print(f"  Report saved: {ctx.output_path}")
    return ctx


# ======================================================================
# CLI
# ======================================================================

def run_cli(args: argparse.Namespace) -> None:
    """Run the pipeline in CLI mode."""

    # Discover plugins
    registry.discover()

    plugin_name = args.plugin or "contact_center"
    plugin = registry.get(plugin_name)

    files = [Path(f) for f in args.files]
    for f in files:
        if not f.exists():
            print(f"Error: file not found: {f}")
            sys.exit(1)

    ctx = PipelineContext(
        plugin=plugin,
        input_files=files,
        output_format=args.format,
    )

    pipeline = ReportPipeline()
    pipeline.add_stage("Cargando archivos", stage_load_data)
    pipeline.add_stage("Validando datos", stage_validate)
    pipeline.add_stage("Combinando datos", stage_combine_data)
    pipeline.add_stage("Calculando KPIs", stage_compute_kpis)
    pipeline.add_stage("Generando gr\u00e1ficos", stage_generate_charts)

    if args.format == "pptx":
        pipeline.add_stage("Generando reporte PPTX", stage_generate_report)

    def on_progress(step: int, total: int, label: str) -> None:
        print(f"\n[{step}/{total}] {label}")

    ctx = pipeline.run(ctx, on_progress=on_progress)

    if ctx.validation_errors:
        print(f"\n\u26a0 Warnings: {len(ctx.validation_errors)} validation errors")

    print(f"\n\u2713 Pipeline complete!")
    if ctx.output_path:
        print(f"  Output: {ctx.output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Report Builder")
    parser.add_argument("--files", nargs="+", help="Input CSV/Excel files")
    parser.add_argument("--plugin", default="contact_center", help="Report plugin name")
    parser.add_argument("--format", choices=["pdf", "pptx"], default="pptx")

    args = parser.parse_args()

    if args.files:
        run_cli(args)
    else:
        print("No files specified. GUI mode not yet implemented.")
        print("Usage: python main.py --files file1.csv file2.csv --format pptx")


if __name__ == "__main__":
    main()
