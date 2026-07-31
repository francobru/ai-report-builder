"""Report generation pipeline.

Orchestrates the full flow:
  files → load → validate → KPIs → charts → AI text → assemble report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from app.core.plugin_registry import ReportPlugin


# ---------------------------------------------------------------------------
# Pipeline context — travels through every stage
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """Mutable bag of data that each pipeline stage reads and writes."""

    plugin: ReportPlugin
    input_files: list[Path]
    output_format: str = "pdf"              # "pdf" | "pptx"
    output_path: Path | None = None
    period_label: str = ""                   # e.g. "Mayo 2026"

    # Populated during execution
    raw_dataframes: dict[str, pd.DataFrame] = field(default_factory=dict)
    combined_data: pd.DataFrame | None = None
    campaign_data: dict[str, pd.DataFrame] = field(default_factory=dict)
    kpi_results: dict[str, Any] = field(default_factory=dict)
    campaign_kpis: dict[str, dict[str, Any]] = field(default_factory=dict)
    chart_images: dict[str, Path] = field(default_factory=dict)
    ai_texts: dict[str, str] = field(default_factory=dict)
    historical_data: dict[str, pd.DataFrame] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

# Type alias for a pipeline stage function
StageFunc = Callable[[PipelineContext], PipelineContext]


class ReportPipeline:
    """Executes a sequence of stages to produce a report.

    Emits progress via an optional callback so the UI can update a
    progress bar.

    Usage::

        pipeline = ReportPipeline()
        pipeline.add_stage("Cargando datos", load_data)
        pipeline.add_stage("Calculando KPIs", compute_kpis)
        ...
        ctx = pipeline.run(ctx, on_progress=update_bar)
    """

    def __init__(self) -> None:
        self._stages: list[tuple[str, StageFunc]] = []

    def add_stage(self, label: str, func: StageFunc) -> "ReportPipeline":
        """Append a named stage.  Returns *self* for chaining."""
        self._stages.append((label, func))
        return self

    def run(
        self,
        ctx: PipelineContext,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> PipelineContext:
        """Execute all stages in order.

        Parameters
        ----------
        ctx:
            The initial pipeline context.
        on_progress:
            Optional ``(current_step, total_steps, label)`` callback.
        """
        total = len(self._stages)
        for idx, (label, func) in enumerate(self._stages, start=1):
            if on_progress:
                on_progress(idx, total, label)
            ctx = func(ctx)
        return ctx
