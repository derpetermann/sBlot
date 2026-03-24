import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from matplotlib import patches
from matplotlib.lines import Line2D

from numpy.typing import NDArray
from core.transforms import rank_clusters_by_likelihood
from core.utils import Extent

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


def fill_outside(
    polygon: NDArray[float],
    color: str | tuple,
    ax: plt.Axes | None = None,
) -> None:
    """Fill the area outside a convex polygon with a solid color.

    Used to mask the area outside the probability simplex in weight and
    preference plots. Splits the polygon into a bottom and top boundary
    and fills between each boundary and the axis edge.

    Note: assumes the polygon is convex and corners are ordered
    consistently (either all clockwise or all counter-clockwise).

    Args:
        polygon: Corner coordinates of the polygon, shape (n_corners, 2).
                 Must have more than 2 corners.
        color: Fill color as a hex string or RGB tuple.
        ax: Matplotlib axis to draw on. Defaults to the current axis.
    Raises:
        ValueError: If polygon has 2 or fewer corners.
    """
    if ax is None:
        ax = plt.gca()

    n_corners = polygon.shape[0]
    if n_corners <= 2:
        raise ValueError('Can only plot polygons with >2 corners')

    # Find leftmost and rightmost corners to split polygon into top and bottom
    i_left = np.argmin(polygon[:, 0])
    i_right = np.argmax(polygon[:, 0])

    # Traverse clockwise from left to right → bottom boundary
    i = i_left
    bot_x = [polygon[i, 0]]
    bot_y = [polygon[i, 1]]
    while i % n_corners != i_right:
        i += 1
        bot_x.append(polygon[i, 0])
        bot_y.append(polygon[i, 1])

    # Traverse counter-clockwise from left to right → top boundary
    i = i_left
    top_x = [polygon[i, 0]]
    top_y = [polygon[i, 1]]
    while i % n_corners != i_right:
        i -= 1
        top_x.append(polygon[i, 0])
        top_y.append(polygon[i, 1])

    # Fill between each boundary and the axis edge
    ymin, ymax = ax.get_ylim()
    ax.fill_between(bot_x, ymin, bot_y, color=color)
    ax.fill_between(top_x, ymax, top_y, color=color)


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
        f'$Z_{{{i + 1}}}: \, \;\;\; {int(lh)}$' for i, lh in enumerate(ranked)
    ]
    # Invisible rectangle used as a header entry in the legend
    header_handle = patches.Rectangle((0, 0), 1, 1, fc="w", fill=False,
                                      edgecolor='none', linewidth=0)
    return labels, [header_handle]

# todo: Rename the function to get confounder_shapes
def get_family_shapes(n_family: int, custom_shapes: list[str] | None = None) -> list[str]:
    """Generate a list of distinct marker shapes for family visualization.

    Selects from matplotlib's filled markers, excluding visually similar
    ones. If custom shapes are provided, they are used first and defaults
    fill the remainder.

    Args:
        n_family: Total number of marker shapes needed.
        custom_shapes: Optional list of matplotlib marker strings to use first.
    Returns:
        List of matplotlib marker strings of length `n_family`.
    Raises:
        ValueError: If more shapes are needed than matplotlib provides.
    """
    # Remove visually ambiguous markers
    available = [m for m in Line2D.filled_markers if m != '8']

    if len(available) < n_family:
        raise ValueError(f"Cannot provide {n_family} distinct shapes — "
                         f"only {len(available)} available.")

    if custom_shapes is None:
        return available[:n_family]

    n_additional = n_family - len(custom_shapes)
    if n_additional <= 0:
        return custom_shapes[:n_family]

    # Fill remaining slots from unused markers in a deterministic order
    remaining = [m for m in available if m not in custom_shapes]
    return custom_shapes + remaining[:n_additional]


def kde_plot(
    x: NDArray[float],
    ax: plt.Axes,
    color: str | tuple | None = None,
    lw: float = 1,
    alpha: float = 0.2,
    clip: tuple[float, float] | None = None,
    z_order: int | None = None,
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
        z_order: Drawing order for all plot elements.
    """
    sns.kdeplot(x, fill=False, color=color, ax=ax, lw=lw, clip=clip, zorder=z_order)

    # Add vertical line at the mean, clipped to the KDE curve height
    kde_line = ax.lines[-1]
    xs = kde_line.get_xdata()
    ys = kde_line.get_ydata()
    mean = np.mean(x)
    height = np.interp(mean, xs, ys)
    ax.vlines(mean, 0, height, color=color, lw=lw, ls=':', zorder=z_order)

    # Shade the area under the curve
    ax.fill_between(xs, 0, ys, facecolor=color, alpha=alpha, zorder=z_order)