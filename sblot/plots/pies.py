import math
import numpy as np

from matplotlib import pyplot as plt
from sbayes.load_data import Data
from sbayes.results import Results
from sblot.config.config_io import Config
from sblot.core.utils import get_cluster_colors, to_folder_name


def plot_pies(
    results: Results,
    data: Data,
    config: Config,
    model: str | None = None
) -> None:
    """Plot cluster membership as pie charts, one per object.

    Each pie chart shows the posterior probability of each object belonging
    to each cluster, arranged in a grid.

    Args:
        results: MCMC results containing cluster samples.
        data: Tuple of (objects, features, confounders).
        config: Combined plot and style configuration.
        model: sBayes model name, e.g., K1 (optional).
    """
    objects, features, confounders = data
    style = config.style.pies
    global_style = config.style.global_

    clusters = np.array(results.clusters)
    n_clusters = clusters.shape[0]
    n_objects = clusters.shape[2]
    n_samples = clusters.shape[1]

    print(clusters.shape, "Shape clusters")
    # Sum cluster assignments over samples — shape: (n_clusters, n_objects)
    samples_per_cluster = np.sum(clusters, axis=1)

    # Resolve cluster colors — cached, guaranteed consistent across plots
    cluster_colors = get_cluster_colors(
        n_clusters=n_clusters,
        custom_colors=config.style.global_.cluster_colors or None,
    )

    # Compute grid dimensions
    n_col = style.output.n_columns
    n_row = math.ceil(n_objects / n_col)

    # Create the figure
    width = style.output.width
    height = style.output.height
    fig, axs = plt.subplots(n_row, n_col, figsize=(width * n_col, height * n_row))
    axs_flat: list[plt.Axes] = fig.axes

    for l in range(n_objects):
        ax: plt.Axes = axs_flat[l]

        # Compute cluster membership counts for this object
        per_object = samples_per_cluster[:, l]
        no_cluster = n_samples - per_object.sum()

        # Build pie slices — one per cluster plus remainder
        slices = per_object.tolist() + [no_cluster]
        colors = cluster_colors[:n_clusters] + [style.pie.no_cluster_color]

        ax.pie(slices, colors=colors, radius=style.pie.radius)

        # Format object label — break long labels at midpoint
        label = str(objects.names[l])
        if (" " in label or "-" in label) and len(label) > style.label.max_label_length:
            split_chars = [i for i, c in enumerate(label) if c in (" ", "-")]
            mid = len(label) / 2
            break_at = min(split_chars, key=lambda i: abs(i - mid))
            if label[break_at] == " ":
                label = label[:break_at] + '\n' + label[break_at + 1:]
            else:
                label = label[:break_at] + '-\n' + label[break_at + 1:]

        # Add object index and name
        ax.text(
            style.axes.index_x, style.axes.label_y,
            str(objects.indices[l] + 1),
            size=style.label.index_size,
            va='center', ha="right",
            transform=ax.transAxes,
        )
        ax.text(
            style.axes.name_x, style.axes.label_y,
            label,
            size=style.label.name_size,
            va='center', ha="left",
            transform=ax.transAxes,
        )

        ax.set_xlim((style.axes.x_min, style.axes.x_max))
        ax.set_ylim((style.axes.y_min, style.axes.y_max))
        ax.axis('off')

    # Hide empty panels
    for e in range(1, n_col * n_row - n_objects + 1):
        axs_flat[-e].axis('off')

    plt.subplots_adjust(
        wspace=style.output.spacing_horizontal,
        hspace=style.output.spacing_vertical,
    )

    # Save the figure
    if model is not None:
        path_out = config.experiment.results.path_out / to_folder_name(model) / 'pies'
    else:
        path_out = config.experiment.results.path_out / 'pies'

    path_out.mkdir(parents=True, exist_ok=True)

    fig.savefig(
        path_out / f'pie_plot.{global_style.format}',
        bbox_inches='tight',
        dpi=global_style.resolution,
        format=global_style.format,
    )
    plt.close(fig)