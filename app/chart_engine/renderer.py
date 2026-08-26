"""Chart renderer \u2014 generates all chart types for the CC report.

Every function returns a ``matplotlib.figure.Figure`` that can be saved
to PNG or embedded in a report.  The caller is responsible for calling
``fig.savefig()`` or passing it to the report generator.

Chart types implemented:
  - bar_line:          Daily distribution (bars) + NA line
  - grouped_bar_line:  Weekday / monthly evolution bars + NA line
  - horizontal_bar:    Campaign volume / skill top-10
  - donut:             Campaign share
  - vertical_bar:      Outbound calls distribution
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from app.chart_engine.chart_styles import (
    ANNOTATION_SIZE,
    BAR_WIDTH,
    DARK_NAVY,
    DONUT_COLORS,
    FIG_DPI,
    FIG_HEIGHT,
    FIG_WIDTH,
    GREEN_LINE,
    HBAR_FIG_HEIGHT,
    LABEL_SIZE,
    MEDIUM_BLUE,
    OUTBOUND_BAR,
    SMALL_FIG_HEIGHT,
    SMALL_FIG_WIDTH,
    TICK_SIZE,
    TITLE_SIZE,
    WHITE,
    apply_global_style,
)

# Apply style on import
apply_global_style()


# ======================================================================
# 1. Daily distribution \u2014 bar + line (pages 3, 4, 7-11)
# ======================================================================

def chart_daily_distribution(
    df: pd.DataFrame,
    title: str = "Distribuci\u00f3n diaria",
    *,
    date_col: str = "date",
    recibidas_col: str = "TOTALCALLS",
    atendidas_col: str = "TRANSFER",
    na_col: str = "PCTATT",
    figsize: tuple[float, float] = (FIG_WIDTH, 4.8),
) -> plt.Figure:
    """Bar chart with Recibidas/Atendidas bars and Nivel de Atenci\u00f3n line."""

    df = df.sort_values(date_col).reset_index(drop=True)
    x = np.arange(len(df))

    fig, ax1 = plt.subplots(figsize=figsize)

    # Bars
    ax1.bar(x - BAR_WIDTH / 2, df[recibidas_col], BAR_WIDTH,
            color=DARK_NAVY, label="Recibidas", zorder=3)
    ax1.bar(x + BAR_WIDTH / 2, df[atendidas_col], BAR_WIDTH,
            color=MEDIUM_BLUE, label="Atendidas", zorder=3)

    # Format left y-axis
    ax1.set_ylabel("")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(_format_thousands))
    ax1.tick_params(axis="y", labelsize=TICK_SIZE)

    # X-axis labels: "1-may", "2-may", ...
    date_labels = _date_labels(df, date_col)
    ax1.set_xticks(x)
    ax1.set_xticklabels(date_labels, rotation=45, ha="right", fontsize=TICK_SIZE)

    # NA line on secondary axis
    ax2 = ax1.twinx()
    na_values = pd.to_numeric(df[na_col], errors="coerce")
    ax2.plot(x, na_values, color=GREEN_LINE, marker="o", markersize=4,
             linewidth=1.8, label="Nivel de Atenci\u00f3n", zorder=4)
    ax2.set_ylim(0, 105)
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax2.tick_params(axis="y", labelsize=TICK_SIZE)
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color("#CCCCCC")

    # Title
    ax1.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", loc="left", pad=12)

    # Gridlines (horizontal only, behind bars)
    ax1.yaxis.grid(True, alpha=0.3, linewidth=0.5, zorder=0)
    ax1.set_axisbelow(True)

    # Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    # Reserve room at the bottom for the rotated date labels, then put the
    # legend underneath them (figure coordinates) so the two never collide.
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.30)
    fig.legend(lines1 + lines2, labels1 + labels2,
               loc="lower center", bbox_to_anchor=(0.5, 0.005),
               ncol=3, frameon=False)
    return fig


# ======================================================================
# 2. Grouped bar + line \u2014 weekday / monthly (pages 5, 12)
# ======================================================================

def chart_grouped_bar_line(
    labels: Sequence[str],
    recibidas: Sequence[float],
    atendidas: Sequence[float],
    nivel_atencion: Sequence[float],
    title: str = "Distribuci\u00f3n por d\u00eda de semana",
    *,
    show_data_labels: bool = True,
    show_na_labels: bool = True,
    y_na_min: float = 50.0,
    figsize: tuple[float, float] = (FIG_WIDTH, FIG_HEIGHT),
) -> plt.Figure:
    """Grouped bars (Rec/Att) with Nivel de Atenci\u00f3n line overlay."""

    x = np.arange(len(labels))
    fig, ax1 = plt.subplots(figsize=figsize)

    bars_rec = ax1.bar(x - BAR_WIDTH / 2, recibidas, BAR_WIDTH,
                       color=DARK_NAVY, label="Recibidas", zorder=3)
    bars_att = ax1.bar(x + BAR_WIDTH / 2, atendidas, BAR_WIDTH,
                       color=MEDIUM_BLUE, label="Atendidas", zorder=3)

    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(_format_thousands))
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=TICK_SIZE)

    # Data labels on bars
    if show_data_labels:
        for bar_set in (bars_rec, bars_att):
            for bar in bar_set:
                h = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width() / 2, h,
                         _fmt_int(h), ha="center", va="bottom",
                         fontsize=ANNOTATION_SIZE, fontweight="bold")

    # NA line
    ax2 = ax1.twinx()
    ax2.plot(x, nivel_atencion, color=GREEN_LINE, marker="o", markersize=5,
             linewidth=2.0, label="Nivel de Atenci\u00f3n", zorder=4)
    ax2.set_ylim(y_na_min, 100)
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color("#CCCCCC")

    if show_na_labels:
        for i, v in enumerate(nivel_atencion):
            ax2.annotate(f"{v:.2f}%".replace(".", ","),
                         (i, v), textcoords="offset points", xytext=(0, 10),
                         ha="center", fontsize=ANNOTATION_SIZE, color=GREEN_LINE,
                         fontweight="bold")

    ax1.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", loc="left", pad=12)
    ax1.yaxis.grid(True, alpha=0.3, linewidth=0.5, zorder=0)
    ax1.set_axisbelow(True)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)
    fig.legend(lines1 + lines2, labels1 + labels2,
               loc="lower center", bbox_to_anchor=(0.5, 0.005),
               ncol=3, frameon=False)
    return fig


# ======================================================================
# 3. Horizontal bar chart \u2014 campaign volume / skills top-10 (pages 6, 14)
# ======================================================================

def chart_horizontal_bars(
    labels: Sequence[str],
    recibidas: Sequence[float],
    atendidas: Sequence[float],
    title: str = "Distribuci\u00f3n por campa\u00f1a",
    *,
    figsize: tuple[float, float] = (FIG_WIDTH, HBAR_FIG_HEIGHT),
) -> plt.Figure:
    """Horizontal paired bars: Recibidas (dark) and Atendidas (light)."""

    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=figsize)

    bars_rec = ax.barh(y + BAR_WIDTH / 2, recibidas, BAR_WIDTH,
                       color=DARK_NAVY, label="Recibidas", zorder=3)
    bars_att = ax.barh(y - BAR_WIDTH / 2, atendidas, BAR_WIDTH,
                       color=MEDIUM_BLUE, label="Atendidas", zorder=3)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=LABEL_SIZE)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_format_thousands))

    # Data labels
    for bars in (bars_rec, bars_att):
        for bar in bars:
            w = bar.get_width()
            ax.text(w + max(recibidas) * 0.01, bar.get_y() + bar.get_height() / 2,
                    _fmt_int(w), va="center", fontsize=ANNOTATION_SIZE, fontweight="bold")

    ax.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", loc="left", pad=12)
    ax.xaxis.grid(True, alpha=0.3, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", fontsize=LABEL_SIZE)

    fig.tight_layout()
    return fig


# ======================================================================
# 4. Donut chart \u2014 campaign share (page 6)
# ======================================================================

def chart_donut(
    labels: Sequence[str],
    values: Sequence[float],
    title: str = "Participaci\u00f3n por campa\u00f1a",
    center_label: str = "",
    center_value: str = "",
    *,
    threshold_pct: float = 0.1,
    figsize: tuple[float, float] = (6.0, 6.0),
) -> plt.Figure:
    """Donut chart with percentage labels.

    Slices below *threshold_pct* are excluded and noted.
    """
    total = sum(values)
    filtered = [(l, v) for l, v in zip(labels, values) if (v / total * 100) >= threshold_pct]
    f_labels, f_values = zip(*filtered) if filtered else ([], [])

    colors = DONUT_COLORS[: len(f_labels)]

    fig, ax = plt.subplots(figsize=figsize)
    wedges, texts, autotexts = ax.pie(
        f_values,
        labels=f_labels,
        autopct=lambda p: f"{p:.0f}%" if p >= 1 else "",
        colors=colors,
        startangle=90,
        pctdistance=0.75,
        wedgeprops={"width": 0.4, "edgecolor": WHITE, "linewidth": 2},
    )

    for t in autotexts:
        t.set_fontsize(LABEL_SIZE)
        t.set_fontweight("bold")
        t.set_color(WHITE)

    for t in texts:
        t.set_fontsize(LABEL_SIZE)
        t.set_fontweight("bold")

    # Center text
    if center_value:
        ax.text(0, 0.05, center_value, ha="center", va="center",
                fontsize=22, fontweight="bold", color=DARK_NAVY)
        ax.text(0, -0.1, center_label, ha="center", va="center",
                fontsize=LABEL_SIZE, color="#666666")

    ax.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", pad=16)
    fig.tight_layout()
    return fig


# ======================================================================
# 5. Simple vertical bar chart \u2014 outbound calls (page 13)
# ======================================================================

def chart_vertical_bars(
    labels: Sequence[str],
    values: Sequence[float],
    title: str = "",
    *,
    show_data_labels: bool = True,
    color: str = OUTBOUND_BAR,
    figsize: tuple[float, float] | None = None,
) -> plt.Figure:
    """Vertical bar chart for single-series data.

    The figure width, label rotation and font size adapt to the number of
    categories, so a full month of daily bars (31 labels) stays readable
    instead of overlapping.
    """
    n = len(labels)

    # Long labels need horizontal room just as much as many labels do
    longest = max((len(str(l)) for l in labels), default=0)

    if figsize is None:
        if n > 20:            # a full month of dates
            figsize = (16.0, 6.0)
        elif n > 10 or longest > 12:
            figsize = (11.0, 6.0)
        else:
            figsize = (SMALL_FIG_WIDTH, SMALL_FIG_HEIGHT)
    if n > 20:
        rotation, tick_fs = 90, max(TICK_SIZE - 3, 8)
    elif n > 10 or longest > 12:
        rotation, tick_fs = 45, max(TICK_SIZE - 1, 9)
    else:
        rotation, tick_fs = 30, TICK_SIZE
    ha = "center" if rotation == 90 else "right"

    x = np.arange(n)
    fig, ax = plt.subplots(figsize=figsize)

    bars = ax.bar(x, values, width=0.6, color=color, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=rotation, ha=ha, fontsize=tick_fs)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_thousands))

    if show_data_labels:
        # With many bars the value labels themselves would collide
        label_fs = ANNOTATION_SIZE if n <= 20 else max(ANNOTATION_SIZE - 3, 7)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h,
                    _fmt_int(h), ha="center", va="bottom",
                    fontsize=label_fs, fontweight="bold")

    if title:
        ax.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", loc="left", pad=12)

    ax.yaxis.grid(True, alpha=0.3, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(x=0.01)

    fig.tight_layout()
    return fig


# ======================================================================
# Save helper
# ======================================================================

def save_chart(fig: plt.Figure, path: Path, close: bool = True) -> Path:
    """Save a figure to *path* at high resolution and optionally close it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path,
        dpi=400,                    # High resolution for crisp PPTX embedding
        facecolor=WHITE,
        bbox_inches="tight",
        pad_inches=0.2,
    )
    if close:
        plt.close(fig)
    return path


# ======================================================================
# Internal formatting helpers
# ======================================================================

def _format_thousands(value: float, _pos: int = 0) -> str:
    """Format axis ticks: 1000 \u2192 '1.000'."""
    if value >= 1000:
        return f"{int(value):,}".replace(",", ".")
    return str(int(value))


def _fmt_int(value: float) -> str:
    """Format a number as integer with dot-thousands: 14552 \u2192 '14.552'."""
    return f"{int(value):,}".replace(",", ".")


def _date_labels(df: pd.DataFrame, date_col: str) -> list[str]:
    """Build '1-may', '2-may', ... labels from a date column."""
    month_names = {
        1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
        7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
    }
    labels = []
    for dt in df[date_col]:
        if pd.isna(dt):
            labels.append("")
        else:
            d = pd.Timestamp(dt)
            labels.append(f"{d.day}-{month_names.get(d.month, '?')}")
    return labels


# ======================================================================
# Outbound calls (llamadas salientes)
# ======================================================================
# Both charts used to share one row, so each was squeezed into ~6 inches and
# its labels ended up around 4 pt on the slide. They now take the full slide
# width, stacked, and are generated at the proportion of the box they land in
# so nothing is scaled down.

def chart_outbound_results(
    labels: Sequence[str],
    values: Sequence[float],
    title: str = "Distribucion por resultado",
    *,
    figsize: tuple[float, float] = (16.0, 2.55),
) -> plt.Figure:
    """Horizontal bars: reason labels read straight, no rotation."""
    order = np.argsort(values)              # largest on top after inverting
    labels = [labels[i] for i in order]
    values = [values[i] for i in order]
    y = np.arange(len(labels))
    total = sum(values) or 1

    fig, ax = plt.subplots(figsize=figsize)
    colors = [DARK_NAVY if v >= max(values) * 0.5 else MEDIUM_BLUE for v in values]
    bars = ax.barh(y, values, height=0.62, color=colors, zorder=3)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=15)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_format_thousands))
    ax.tick_params(axis="x", labelsize=13)

    span = max(values) if len(values) else 1
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + span * 0.012,
                bar.get_y() + bar.get_height() / 2,
                _fmt_int(v) + "  (" + f"{v / total * 100:.1f}".replace(".", ",") + "%)",
                va="center", fontsize=14, fontweight="bold")

    ax.set_xlim(0, span * 1.16)
    ax.set_title(title, fontsize=18, fontweight="bold", loc="left", pad=12)
    ax.xaxis.grid(True, alpha=0.25, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return fig


def chart_outbound_daily(
    labels: Sequence[str],
    values: Sequence[float],
    title: str = "Distribucion diaria - Llamadas salientes",
    *,
    figsize: tuple[float, float] = (16.0, 2.95),
) -> plt.Figure:
    """Daily volume across the full slide width.

    With many days the value labels are thinned out (every other bar) instead
    of shrinking the font until nothing can be read.
    """
    n = len(labels)
    x = np.arange(n)
    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.bar(x, values, width=0.62, color=DARK_NAVY, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=90 if n > 20 else 45,
                       ha="center" if n > 20 else "right", fontsize=12)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_thousands))
    ax.tick_params(axis="y", labelsize=12)

    paso = 1 if n <= 16 else 2              # label every other bar when crowded
    for i, bar in enumerate(bars):
        if i % paso:
            continue
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h, _fmt_int(h),
                ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylim(0, max(values) * 1.16 if len(values) else 1)
    ax.set_title(title, fontsize=18, fontweight="bold", loc="left", pad=12)
    ax.yaxis.grid(True, alpha=0.25, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(x=0.01)
    fig.tight_layout()
    return fig
