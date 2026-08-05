"""Charts for the Plan Medico monthly report.

Uses the palette of the original May 2026 Plan Medico template, which
differs from the Contact Center report: blue / light blue bars with a
lime-green attention line, and purple bars for the PM Consultas section.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from app.chart_engine.chart_styles import apply_global_style

apply_global_style()


# ======================================================================
# Palette (from the Plan Medico template)
# ======================================================================
PM_BLUE = "#2F5FD0"        # Recibidas
PM_LIGHT_BLUE = "#4FC3F7"  # Atendidas
PM_GREEN = "#8BC34A"       # Nivel de atencion line / positive
PM_RED = "#F44336"         # No atendidas
PM_PURPLE = "#7C4DFF"      # PM Consultas section
PM_GRAY = "#6B7280"
WHITE = "#FFFFFF"

TITLE_SIZE = 17
TICK_SIZE = 12
LABEL_SIZE = 12
ANNOT_SIZE = 11


def _fmt_int(v: float) -> str:
    return f"{int(round(v)):,}".replace(",", ".")


def _thousands(v: float, _pos: int = 0) -> str:
    return _fmt_int(v) if v >= 1000 else str(int(v))


# ======================================================================
# Daily distribution (sections 1, 2 and 3a)
# ======================================================================

def chart_pm_daily(
    df: pd.DataFrame,
    title: str,
    *,
    bar_color: str = PM_BLUE,
    figsize: tuple[float, float] = (16.0, 5.2),
    show_values: bool = True,
) -> plt.Figure:
    """Daily Recibidas/Atendidas bars with the attention-level line.

    The x axis shows the day number only, as in the template.
    """
    df = df.sort_values("date").reset_index(drop=True)
    x = np.arange(len(df))
    width = 0.4

    fig, ax1 = plt.subplots(figsize=figsize)

    b1 = ax1.bar(x - width / 2, df["TOTALCALLS"], width,
                 color=bar_color, label="Recibidas", zorder=3)
    ax1.bar(x + width / 2, df["TRANSFER"], width,
            color=PM_LIGHT_BLUE, label="Atendidas", zorder=3)

    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(_thousands))
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{pd.Timestamp(d).day:02d}" for d in df["date"]],
                        fontsize=TICK_SIZE)
    ax1.set_xlabel("Dia del mes", fontsize=LABEL_SIZE, color=PM_GRAY)

    if show_values:
        for bar in b1:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h, _fmt_int(h),
                     ha="center", va="bottom", fontsize=ANNOT_SIZE, fontweight="bold")

    ax2 = ax1.twinx()
    na = pd.to_numeric(df["PCTATT"], errors="coerce")
    ax2.plot(x, na, color=PM_GREEN, marker="o", markersize=6,
             markerfacecolor=WHITE, markeredgewidth=2,
             linewidth=2.2, label="Nivel de Atencion", zorder=4)
    ax2.set_ylim(50, 102)
    ax2.set_ylabel("NA (%)", fontsize=LABEL_SIZE, color=PM_GREEN)
    ax2.tick_params(axis="y", colors=PM_GREEN, labelsize=TICK_SIZE)
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color("#CCCCCC")

    ax1.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", loc="left", pad=14)
    ax1.yaxis.grid(True, alpha=0.25, linewidth=0.6, zorder=0)
    ax1.set_axisbelow(True)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.20)
    fig.legend(h1 + h2, l1 + l2, loc="lower center",
               bbox_to_anchor=(0.5, 0.005), ncol=3, frameon=False,
               fontsize=LABEL_SIZE)
    return fig


# ======================================================================
# Top closure reasons (section 3b)
# ======================================================================

def chart_top_reasons(
    labels: Sequence[str],
    values: Sequence[float],
    percents: Sequence[float],
    title: str,
    *,
    figsize: tuple[float, float] = (15.0, 7.5),
    highlight_top: int = 4,
) -> plt.Figure:
    """Horizontal bars of the most frequent closure reasons.

    The leading reasons are drawn in the darker blue, as in the template.
    """
    y = np.arange(len(labels))
    colors = [PM_BLUE if i < highlight_top else PM_LIGHT_BLUE
              for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.barh(y, values, height=0.62, color=colors, zorder=3)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=LABEL_SIZE)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_thousands))

    span = max(values) if len(values) else 1
    for bar, v, p in zip(bars, values, percents):
        ax.text(bar.get_width() + span * 0.015,
                bar.get_y() + bar.get_height() / 2,
                f"{_fmt_int(v)}  ({p:.1f}%)".replace(".", ","),
                va="center", fontsize=ANNOT_SIZE, fontweight="bold")

    ax.set_xlim(0, span * 1.18)
    ax.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", loc="left", pad=14)
    ax.xaxis.grid(True, alpha=0.25, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    return fig


def save_chart(fig: plt.Figure, path: Path, close: bool = True) -> Path:
    """Save a figure at high resolution."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=400, facecolor=WHITE, bbox_inches="tight", pad_inches=0.2)
    if close:
        plt.close(fig)
    return path
