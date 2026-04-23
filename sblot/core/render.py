import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from matplotlib import patches

from numpy.typing import NDArray
from sblot.core.transforms import rank_clusters_by_likelihood
from sblot.core.utils import Extent

# Default colors and color
PREF_COLOR_MAP = sns.cubehelix_palette(light=1, start=.5, rot=-.75, as_cmap=True)
COLOR_NEUTRAL = "rgba(150, 150, 150, 0.4)"  # unassigned objects, isolates
COLOR_HIGHLIGHT = "#990055"                   # selected families, features


def annotate_label(
    xy: NDArray[float],
    label: int | str,
    color: str,
    offset_x: float,
    offset_y: float,
    ax: plt.Axes,
    fontsize: int = 10,
) -> None:
    """Annotate a single site label on a map axis.

    Places a text label at a given location with a small offset so it does
    not overlap with the point marker underneath.

    Args:
        xy: (x, y) coordinates of the site in map CRS units.
        label: Text or number to display, typically the site index.
        color: Label color as a hex string or named color.
        offset_x: Horizontal offset in map CRS units.
        offset_y: Vertical offset in map CRS units.
        ax: Matplotlib axis to annotate.
        fontsize: Font size of the label.
    """
    x = float(xy[0]) + offset_x
    y = float(xy[1]) + offset_y
    ax.annotate(label, xy=(x, y), fontsize=fontsize, color=color)


def style_axes(extent: Extent, ax: plt.Axes) -> None:
    """Style a map axis by setting spatial extent and removing tick labels.

    Args:
        extent: Spatial extent defining the axis limits.
        ax: Matplotlib axis to style.
    """
    ax.set_xlim(extent.x_min, extent.x_max)
    ax.set_ylim(extent.y_min, extent.y_max)
    ax.set_xticks([])
    ax.set_yticks([])


def make_likelihood_legend(likelihood_single_clusters: dict) -> tuple[list[str], list]:
    """Build legend labels and handles ranked by mean log-likelihood.

    Args:
        likelihood_single_clusters: Dict mapping cluster names to arrays of
                                    log-likelihood values.
    Returns:
        Tuple of (labels, handles) for use with ax.legend().
    """
    ranked = rank_clusters_by_likelihood(likelihood_single_clusters)
    labels = ["      log-likelihood per cluster"] + [
        f'$Z_{{{i + 1}}}: \\, \\;\\;\\; {int(lh)}$'
        for i, (_, lh) in enumerate(ranked)
    ]
    # Invisible rectangle used as a header entry in the legend
    header_handle = patches.Rectangle((0, 0), 1, 1, fc="w", fill=False,
                                      edgecolor='none', linewidth=0)
    return labels, [header_handle]


def kdeplot_with_mean(
    x: NDArray[float],
    ax: plt.Axes,
    color: str | tuple | None = None,
    lw: float = 1,
    alpha: float = 0.2,
    clip: tuple[float, float] | None = None,
    zorder: int | None = None,
) -> None:
    """Plot a KDE curve with a vertical mean line and shaded fill.

    Extends seaborn's kdeplot with a dotted vertical line at the mean
    and a semi-transparent fill under the curve.

    Args:
        x: 1D array of samples to plot.
        ax: Matplotlib axis to draw on.
        color: Line and fill color as a hex string or RGB tuple.
        lw: Line width of the KDE curve and mean line.
        alpha: Opacity of the fill under the curve.
        clip: Optional (min, max) tuple to clip the KDE estimate.
        zorder: Drawing order for all plot elements.
    """
    sns.kdeplot(x, fill=False, color=color, ax=ax, lw=lw, clip=clip, zorder=zorder)

    # Add vertical line at the mean, clipped to the KDE curve height
    kde_line = ax.lines[-1]
    xs = kde_line.get_xdata()
    ys = kde_line.get_ydata()
    mean = np.mean(x)
    height = np.interp(mean, xs, ys)
    ax.vlines(mean, 0, height, color=color, lw=lw, ls=':', zorder=zorder)

    # Shade the area under the curve
    ax.fill_between(xs, 0, ys, facecolor=color, alpha=alpha, zorder=zorder)
