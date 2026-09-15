# one chart style for every figure in results/figures, so the walkthrough
# reads as one system. light surface, thin marks, recessive grid, a fixed
# categorical order, one blue ramp for magnitude and blue against red for sign

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter

from loop.spec import FIGURES_DIR

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGING = ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f3a6a5", "#e34948", "#a32626"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BAND = "#cde2fb"


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "text.color": INK,
        "axes.labelcolor": INK2,
        "axes.labelsize": 9,
        "axes.titlesize": 11,
        "axes.titleweight": "normal",
        "axes.titlelocation": "left",
        "font.size": 9,
        "lines.linewidth": 1.6,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "savefig.dpi": 160,
        "axes.prop_cycle": plt.cycler(color=SERIES),
    })


def figure(title, subtitle=None, size=(9, 5), rows=1, cols=1, **kwargs):
    style()
    fig, axes = plt.subplots(rows, cols, figsize=size, **kwargs)
    # the subtitle sits a fixed distance under the title in inches, so short
    # figures do not push the two lines into each other
    top = 0.995
    fig.suptitle(title, x=0.01, y=top, ha="left", va="top", fontsize=12, color=INK)
    if subtitle:
        fig.text(0.01, top - 0.28 / fig.get_figheight(), subtitle, ha="left", va="top", fontsize=9, color=INK2)
    return fig, axes


def save(fig, name):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    return path


# a label at the right end of a line, in ink, next to a mark of the series color
def label_end(ax, x, y, text, color):
    ax.plot([x], [y], marker="o", markersize=4, color=color, zorder=5)
    ax.annotate(text, (x, y), xytext=(5, 0), textcoords="offset points", va="center", fontsize=8, color=INK2)


def pct_axis(ax, axis="y", decimals=0):
    fmt = FuncFormatter(lambda v, _: f"{v:.{decimals}f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def sequential_cmap():
    return LinearSegmentedColormap.from_list("loop_sequential", SEQUENTIAL)


def diverging_cmap():
    return LinearSegmentedColormap.from_list("loop_diverging", DIVERGING)
