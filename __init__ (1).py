"""Typed configuration loaded from YAML and validated with Pydantic."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    name: str = "AI Report Builder"
    version: str = "1.0.0"
    language: str = "es"


class PathsConfig(BaseModel):
    templates: str = "templates"
    output: str = "output"
    historical_data: str = "data/historical"


class CsvConfig(BaseModel):
    separator: str = ";"
    decimal: str = ","
    encoding: str = "utf-8"
    date_format: str = "%d/%m/%Y"


class AIConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 2000
    temperature: float = 0.3
    language: str = "es"
    api_key: Optional[str] = Field(default=None, exclude=True)


class ChartColors(BaseModel):
    recibidas: str = "#1B3A5C"
    atendidas: str = "#5B9BD5"
    nivel_atencion: str = "#4CAF50"
    abandono: str = "#E74C3C"
    background: str = "#FFFFFF"


class ChartFonts(BaseModel):
    family: str = "Calibri"
    title_size: int = 14
    label_size: int = 10
    tick_size: int = 9


class ChartFigure(BaseModel):
    dpi: int = 200
    bar_width: float = 0.35


class ChartsConfig(BaseModel):
    colors: ChartColors = ChartColors()
    fonts: ChartFonts = ChartFonts()
    figure: ChartFigure = ChartFigure()


class ReportConfig(BaseModel):
    header_color: str = "#1B3A5C"
    accent_color: str = "#4CAF50"
    negative_color: str = "#E74C3C"
    font_family: str = "Calibri"
    page_footer_left: str = "Hospital Alemán · Fuente: Tecnovoz"


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------

class Settings(BaseModel):
    """Root configuration object.  Instantiate via ``Settings.load(path)``."""

    app: AppConfig = AppConfig()
    paths: PathsConfig = PathsConfig()
    csv: CsvConfig = CsvConfig()
    ai: AIConfig = AIConfig()
    charts: ChartsConfig = ChartsConfig()
    report: ReportConfig = ReportConfig()

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> "Settings":
        """Load settings from a YAML file.

        Falls back to ``config/settings.yaml`` relative to the project root
        if *config_path* is not provided.
        """
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            return cls()

        with open(config_path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        return cls.model_validate(raw)


# Module-level singleton — imported by other modules as ``from app.config import settings``.
settings = Settings.load()
