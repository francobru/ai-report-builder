"""PPTX report generator — Python wrapper for the pptxgenjs script.

Builds a JSON configuration from pipeline context and calls the
Node.js script to generate the PowerPoint file.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.core.pipeline import PipelineContext


SCRIPT_PATH = Path(__file__).parent / "generate_pptx.js"


def generate_pptx(ctx: PipelineContext, output_path: Path) -> Path:
    """Generate a PPTX report from the pipeline context.

    Parameters
    ----------
    ctx:
        Completed pipeline context with KPIs, charts, and AI texts.
    output_path:
        Where to save the .pptx file.

    Returns
    -------
    Path
        The path to the generated .pptx file.
    """
    config = _build_config(ctx, output_path)

    # Write config to temp file
    config_path = output_path.parent / "_pptx_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Call Node.js
    result = subprocess.run(
        ["node", str(SCRIPT_PATH), str(config_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"PPTX generation failed:\n{result.stderr}")

    # Clean up config
    config_path.unlink(missing_ok=True)

    return output_path


def _build_config(ctx: PipelineContext, output_path: Path) -> dict[str, Any]:
    """Transform pipeline context into the JSON structure the JS script expects."""

    config: dict[str, Any] = {
        "period": ctx.period_label,
        "output_path": str(output_path),
        "total_pages": 19,
        "charts": {},
    }

    # Global KPIs
    if "global" in ctx.kpi_results:
        config["global_kpis"] = _format_kpis(ctx.kpi_results["global"])

    # Global variations
    if "global" in ctx.kpi_results and "global_variations" in ctx.kpi_results:
        config["global_variations"] = _format_variations(ctx.kpi_results["global_variations"])

    # All campaigns aggregate
    if "all_campaigns" in ctx.campaign_kpis:
        config["all_campaigns"] = {
            "kpis": _format_kpis(ctx.campaign_kpis["all_campaigns"]),
            "chart_path": str(ctx.chart_images.get("daily_all_campaigns", "")),
        }

    # All without Gipfel
    if "all_no_gipfel" in ctx.campaign_kpis:
        config["all_no_gipfel"] = {
            "kpis": _format_kpis(ctx.campaign_kpis["all_no_gipfel"]),
            "chart_path": str(ctx.chart_images.get("daily_all_no_gipfel", "")),
        }

    # Individual campaigns
    campaigns = []
    for camp_name in ["Conmutador", "Plan Médico", "Portal", "Turnos", "Agendas"]:
        if camp_name in ctx.campaign_kpis:
            chart_key = f"daily_{camp_name.lower().replace(' ', '_')}"
            campaigns.append({
                "name": camp_name,
                "kpis": _format_kpis(ctx.campaign_kpis[camp_name]),
                "variations": _format_variations(ctx.campaign_kpis.get(f"{camp_name}_variations", {})),
                "chart_path": str(ctx.chart_images.get(chart_key, "")),
            })
    config["campaigns"] = campaigns

    # Chart paths
    for chart_id, chart_path in ctx.chart_images.items():
        config["charts"][chart_id] = str(chart_path)

    # Skill table
    if "skill_table" in ctx.kpi_results:
        config["skill_table"] = ctx.kpi_results["skill_table"]

    # Outbound
    if "outbound" in ctx.kpi_results:
        config["outbound"] = ctx.kpi_results["outbound"]

    # AI texts
    config["ai_texts"] = ctx.ai_texts

    return config


def _format_kpis(kpis: dict[str, dict]) -> dict[str, str]:
    """Extract formatted values from KPI results dict."""
    return {kpi_id: data.get("formatted", "—") for kpi_id, data in kpis.items()}


def _format_variations(variations: dict[str, dict]) -> dict[str, str]:
    """Extract formatted variation strings."""
    return {kpi_id: data.get("formatted", "") for kpi_id, data in variations.items()}
