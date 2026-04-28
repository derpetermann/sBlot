import logging
import math
import numpy as np
import seaborn as sns

from matplotlib import pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from numpy.typing import NDArray
from sbayes.results import Results
from sblot.config.config_io import Config
from sblot.core.render import kdeplot_with_mean, PREF_COLOR_MAP
from sblot.core.utils import get_corner_points, to_folder_name



def plot_weights_simplex(
    samples: NDArray[float],
    feature: str,
    ax: plt.Axes,
    config: Config,
    labels: list[str],
    mean_weights: bool = True,
) -> None:
    """Plot a single weight vector in a 2D simplex representation.

    Args:
        samples: Sampled weight vectors, shape (n_samples, n_weights).
        feature: Name of the feature being plotted.
        ax: Matplotlib axis to draw on.
        config: Combined plot and style configuration.
        labels: Corner labels for the simplex, e.g. ['A', 'F', 'U'].
        mean_weights: Whether to plot the mean weight as a dot.
    """
    # Filter out non-finite samples
    valid = np.all(np.isfinite(samples), axis=1)
    samples = samples[valid]
    n_samples, n_weights = samples.shape
    style = config.style.weights

    # Add feature name as title
    if style.legend.title.add:
        ax.text(
            style.legend.title.position.x,
            style.legend.title.position.y,
            str(feature),
            fontdict={'fontweight': 'bold', 'fontsize': style.legend.title.font_size},
            transform=ax.transAxes,
        )

    if n_weights == 1:
        logging.warning("Weights can't be plotted in a model without confounders.")

    elif n_weights == 2:
        x = samples.T[1]
        kdeplot_with_mean(x, color=style.simplex.color, ax=ax,
                          lw=style.simplex.border_width, clip=(0, 1))

        ax.axes.get_yaxis().set_visible(False)

        # Add corner labels
        if style.legend.corner_labels.add:
            for i, label in enumerate(labels):
                x_pos = 0.05 if i == 0 else 0.95
                ax.text(
                    x_pos, -0.05, label,
                    ha='center', va='top',
                    fontdict={'fontsize': style.legend.corner_labels.font_size},
                    transform=ax.transAxes,
                )

        ax.plot([0, 1], [0, 0], lw=style.simplex.border_width,
                color=style.simplex.color, clip_on=False)
        ax.set_ylim(bottom=0)
        ax.set_xlim((-0.01, 1.01))
        ax.axis('off')

    else:
        # Compute simplex corners
        corners = get_corner_points(n_weights)
        xmin, ymin = np.min(corners, axis=0)
        xmax, ymax = np.max(corners, axis=0)

        # Project samples onto 2D simplex
        samples_projected = samples.dot(corners)
        x = samples_projected.T[0]
        y = samples_projected.T[1]

        # Create the simplex path for clipping only
        clip_patch = MplPolygon(corners, closed=True, transform=ax.transData)

        # KDE density plot
        sns.kdeplot(
            x=x, y=y,
            fill=True, cut=30, levels=20,
            clip=((xmin, xmax), (ymin, ymax)),
            cmap=PREF_COLOR_MAP, ax=ax,
        )

        # Clip all artists to the simplex path
        for artist in ax.get_children():
            artist.set_clip_path(clip_patch)

        # Draw simplex outline on top
        ax.fill(*corners.T, edgecolor='k', facecolor='none',
                lw=style.simplex.border_width, zorder=10)

        # Plot mean weight
        if mean_weights:
            mean_projected = np.mean(samples, axis=0).dot(corners)
            ax.scatter(
                *mean_projected.T,
                color=style.mean.color,
                s=style.mean.size,
                marker=style.mean.marker,
                lw=0,
                zorder=20
            )

        # Add corner labels outside the clip path
        if style.legend.corner_labels.add:
            for xy, label in zip(corners, labels):
                xy = xy * style.simplex.label_stretch - 0.05
                ax.text(
                    float(xy[0]), float(xy[1]), str(label),
                    ha='center', va='center',
                    fontdict={'fontsize': style.legend.corner_labels.font_size},
                )

        padding = style.simplex.padding
        ax.set_xlim((xmin - padding, xmax + padding))
        ax.set_ylim((ymin - padding, ymax + padding))
        ax.axis('off')


def plot_weights(
    results: Results,
    config: Config,
    model: str | None = None,
    verbose: bool = True
) -> None:
    """Plot all weight simplices arranged in a grid and save to file.

    Creates one simplex panel per feature, arranged in a grid of n_columns
    columns. Empty panels are hidden. The figure is saved to path_out.

    Args:
        results: MCMC results containing weight samples for each feature.
        config: Combined plot and style configuration.
        model: sBayes model name, e.g., K1 (optional).
        verbose: If True, print a progress message. Default is True.
    """
    if verbose:
        print("Plotting weights...")

    experiment = config.experiment.plots.weights
    style = config.style.weights
    global_style = config.style.global_

    # Filter to requested features, or use all if none specified
    weights = results.weights

    if experiment.features:
        weights = {f: weights[f] for f in experiment.features}

    # Resolve corner labels
    labels = style.legend.corner_labels.resolve_names(results)

    # Compute grid dimensions
    n_plots = len(weights)
    n_col = style.output.n_columns
    n_row = math.ceil(n_plots / n_col)

    # Create the figure
    width = style.output.width_subplot
    height = style.output.height_subplot
    fig, axs = plt.subplots(n_row, n_col, figsize=(width * n_col, height * n_row))

    # Ensure axs is always a flat list of Axes
    axs_flat: list[plt.Axes] = fig.axes

    # Hide empty panels
    n_empty = n_row * n_col - n_plots
    for e in range(1, n_empty + 1):
        axs_flat[-e].axis('off')

    # Plot one simplex per feature
    for position, (f, samples) in enumerate(weights.items()):
        plot_weights_simplex(
            samples=samples,
            feature=f,
            ax=axs_flat[position],
            config=config,
            labels=labels,
            mean_weights=True,
        )
        if verbose:
            print(f"{position + 1} of {n_plots} plots finished")

    plt.subplots_adjust(
        wspace=style.output.spacing_horizontal,
        hspace=style.output.spacing_vertical,
    )

    # Save the figure
    if model is not None:
        path_out = config.experiment.results.path_out / to_folder_name(model) / 'weights'
    else:
        path_out = config.experiment.results.path_out / 'weights'

    path_out.mkdir(parents=True, exist_ok=True)

    fig.savefig(
        path_out / f'weights_grid.{global_style.format}',
        bbox_inches='tight',
        dpi=global_style.resolution,
        format=global_style.format,
    )
    plt.close(fig)


def infer_component_labels(results: Results) -> list[str]:
    """Infer simplex corner labels from component names.

    Uses the first letter of each component name, capitalised.
    The areal effect is always labelled 'A'.

    Args:
        results: MCMC results defining the components.
    Returns:
        Ordered list of single-letter labels, e.g. ['A', 'F', 'U'].
    """
    labels = ["A"] + [c[0].upper() for c in results.confounders]
    if len(set(labels)) < len(labels):
        import warnings
        warnings.warn(
            "Two or more component labels are identical. "
            "Consider providing explicit label names in config_style.yaml."
        )
    return labels