"""Fixed chart styles for the Hospital Alemán Contact Center report.

These values are IMMUTABLE across months.  Every chart must use them
so the visual output is identical between reports.

Colors, fonts, sizes, and layout constants are all defined here.
Individual chart renderers import from this module — never hardcode
style values elsewhere.
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager


# ======================================================================
# Color palette — extracted from the PDF report
# ======================================================================

DARK_NAVY = "#1B3A5C"         # Recibidas bars, header backgrounds
MEDIUM_BLUE = "#5B9BD5"       # Atendidas bars
GREEN_LINE = "#4CAF50"        # Nivel de Atención line
RED_ACCENT = "#E74C3C"        # Negative variation arrows
GREEN_ACCENT = "#27AE60"      # Positive variation arrows
LIGHT_GRAY_BG = "#F5F6F8"    # Card backgrounds
WHITE = "#FFFFFF"
TEXT_DARK = "#2C3E50"         # Main text
TEXT_GRAY = "#7F8C8D"         # Secondary text

# Donut / pie chart palette (campaign share)
DONUT_COLORS = [
    DARK_NAVY,      # Turnos (largest)
    "#3A6EA5",      # Conmutador
    MEDIUM_BLUE,    # Plan Médico
    "#8DB4E2",      # Portal
    "#B8D4F0",      # Agendas / small
    "#D6E8F7",      # Camp HA / tiny
]

# Outbound calls bar color
OUTBOUND_BAR = DARK_NAVY


# ======================================================================
# Typography
# ======================================================================

FONT_FAMILY = "Calibri"
FONT_FALLBACK = "DejaVu Sans"   # Available on all systems

# Sizes (in points) — large enough to be readable in PPTX
TITLE_SIZE = 18
SUBTITLE_SIZE = 14
LABEL_SIZE = 13
TICK_SIZE = 12
ANNOTATION_SIZE = 11
LEGEND_SIZE = 12


# ======================================================================
# Figure dimensions — sized for high-quality PPTX embedding
# ======================================================================

# Standard chart area (wide format, fills PPTX slide)
FIG_WIDTH = 16.0              # inches
FIG_HEIGHT = 7.0              # inches
FIG_DPI = 300                 # high resolution for sharp output

# Horizontal bar chart (taller)
HBAR_FIG_HEIGHT = 8.0

# Small chart (e.g. outbound result distribution)
SMALL_FIG_WIDTH = 7.0
SMALL_FIG_HEIGHT = 7.0

# Bar widths
BAR_WIDTH = 0.35
BAR_GAP = 0.02


# ======================================================================
# Global matplotlib configuration
# ======================================================================

def apply_global_style() -> None:
    """Apply the HA report style globally to matplotlib.

    Call this once at application startup.
    """
    # Try to use Calibri; fall back to DejaVu Sans
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = FONT_FAMILY if FONT_FAMILY in available else FONT_FALLBACK

    mpl.rcParams.update({
        # Font
        "font.family": "sans-serif",
        "font.sans-serif": [font, "DejaVu Sans", "Arial"],
        "font.size": LABEL_SIZE,

        # Axes
        "axes.titlesize": TITLE_SIZE,
        "axes.titleweight": "bold",
        "axes.labelsize": LABEL_SIZE,
        "axes.labelcolor": TEXT_DARK,
        "axes.edgecolor": "#CCCCCC",
        "axes.linewidth": 0.5,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,

        # Ticks
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "xtick.color": TEXT_GRAY,
        "ytick.color": TEXT_GRAY,

        # Legend
        "legend.fontsize": LEGEND_SIZE,
        "legend.frameon": False,

        # Figure
        "figure.facecolor": WHITE,
        "figure.dpi": FIG_DPI,
        "savefig.dpi": FIG_DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.15,

        # Grid (off by default, enabled per chart if needed)
        "grid.alpha": 0.3,
        "grid.linewidth": 0.5,
    })
