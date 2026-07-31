"""AI Engine — builds prompts from KPI data and calls the Claude API.

The AI is used ONLY for:
  - Executive summary
  - Conclusions
  - Recommendations
  - Anomaly detection
  - Trend explanations

It NEVER invents data.  If data is missing, it must say so.
"""

from __future__ import annotations

import os
from typing import Any

from app.config import settings
from app.core.plugin_registry import PromptConfig


class AIEngine:
    """Thin wrapper around the Anthropic API.

    Instantiate with an API key (or set ``ANTHROPIC_API_KEY`` env var).
    If no key is available, all methods return a placeholder string so
    the report can still be generated without AI text.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.ai.api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None
        self._model = settings.ai.model
        self._max_tokens = settings.ai.max_tokens
        self._temperature = settings.ai.temperature

        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                print("[AIEngine] anthropic package not installed — AI text disabled.")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_executive_summary(
        self,
        prompt_config: PromptConfig,
        kpi_summary: str,
        period: str,
    ) -> str:
        """Generate an executive summary from KPI data."""
        prompt = prompt_config.executive_summary.format(
            kpi_summary=kpi_summary,
            period=period,
        )
        return self._call(prompt)

    def generate_conclusions(
        self,
        prompt_config: PromptConfig,
        kpi_summary: str,
        period: str,
    ) -> str:
        """Generate conclusions based on KPI analysis."""
        prompt = prompt_config.conclusions.format(
            kpi_summary=kpi_summary,
            period=period,
        )
        return self._call(prompt)

    def generate_recommendations(
        self,
        prompt_config: PromptConfig,
        conclusions: str,
        period: str,
    ) -> str:
        """Generate recommendations based on conclusions."""
        prompt = prompt_config.recommendations.format(
            conclusions=conclusions,
            period=period,
        )
        return self._call(prompt)

    def detect_anomalies(
        self,
        prompt_config: PromptConfig,
        daily_data: str,
        period: str,
    ) -> str:
        """Detect anomalies in daily data."""
        prompt = prompt_config.anomaly_detection.format(
            daily_data=daily_data,
            period=period,
        )
        return self._call(prompt)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call(self, prompt: str) -> str:
        """Send a prompt to Claude and return the response text."""
        if not self.is_available:
            return "(Texto generado por IA no disponible — configure ANTHROPIC_API_KEY)"

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            return f"(Error al generar texto con IA: {e})"


def build_kpi_summary(kpis: dict[str, dict], variations: dict[str, dict] | None = None) -> str:
    """Format KPI results as a readable string for inclusion in prompts.

    Example output::

        - Recibidas: 77.530 (▼ 7,37% vs mes anterior)
        - Atendidas: 69.740 (▼ 5,60% vs mes anterior)
        - Nivel de Atención: 89,95% (▲ 1,91% vs mes anterior)
    """
    lines: list[str] = []
    for kpi_id, data in kpis.items():
        line = f"- {data['label']}: {data['formatted']}"
        if data.get("unit") and data["unit"] not in data["formatted"]:
            line += f" {data['unit']}"
        if variations and kpi_id in variations:
            var = variations[kpi_id]
            if var["formatted"] != "—":
                line += f" ({var['formatted']} vs mes anterior)"
        lines.append(line)
    return "\n".join(lines)


def build_daily_data_summary(df: Any) -> str:
    """Format a DataFrame's daily data as a text table for the anomaly prompt."""
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        return str(df)

    cols = ["date", "TOTALCALLS", "TRANSFER", "PCTATT"]
    available = [c for c in cols if c in df.columns]
    subset = df[available].copy()

    if "date" in subset.columns:
        subset["date"] = pd.to_datetime(subset["date"]).dt.strftime("%d/%m/%Y")

    return subset.to_string(index=False)
