import math
import numpy as np

from matplotlib import pyplot as plt, colors as mcolors
from numpy.typing import NDArray
from sbayes.load_data import Data, Confounder
from sbayes.results import Results
from sblot.config.config_io import Config, PiesConfig
from sblot.core.render import kdeplot_with_mean
from sblot.core.utils import get_cluster_colors, to_folder_name, run_suffix


def break_label(label: str, max_length: int) -> str:
    """Break a long label into two lines at the space or hyphen nearest its middle."""
    if (" " in label or "-" in label) and len(label) > max_length:
        split_chars = [i for i, c in enumerate(label) if c in (" ", "-")]
        mid = len(label) / 2
        break_at = min(split_chars, key=lambda i: abs(i - mid))
        if label[break_at] == " ":
            return label[:break_at] + '\n' + label[break_at + 1:]
        return label[:break_at] + '-\n' + label[break_at + 1:]
    return label


def confounder_label(confounder: Confounder, object_idx: int, max_length: int) -> str | None:
    """Return the confounder group(s) of an object as a label, or None if it has none."""
    groups = [
        str(name)
        for name, assigned in zip(confounder.group_names, confounder.group_assignment[:, object_idx])
        if assigned and str(name) != '<ALL>'
    ]
    if not groups:
        return None
    return break_label(', '.join(groups), max_length)


def panel_layout(
    clusters: NDArray[float],
    pies: PiesConfig,
    n_columns: int,
) -> tuple[int, int, list[tuple[int, int] | None]]:
    """Decide which object and highlighted cluster goes into each panel.

    Args:
        clusters: Cluster samples, shape (n_samples, n_clusters, n_objects).
        pies: Pie plot configuration.
        n_columns: Number of columns when not grouping by cluster.
    Returns:
        Tuple of (n_rows, n_columns, panels), where panels holds one
        (object index, highlighted cluster) pair or None per grid cell, row by row.
    """
    _, n_clusters, n_objects = clusters.shape

    if not pies.group_by_cluster:
        main_cluster = np.argmax(np.mean(clusters, axis=0), axis=0)
        n_rows = math.ceil(n_objects / n_columns)
        panels = [(i, int(main_cluster[i])) for i in range(n_objects)]
        panels += [None] * (n_rows * n_columns - n_objects)
        return n_rows, n_columns, panels

    # One row per cluster, with the objects sorted by their median membership
    median = np.median(clusters, axis=0)  # shape: (n_clusters, n_objects)
    rows = []
    for c in range(n_clusters):
        members = np.flatnonzero(median[c] >= pies.group_by_cluster_threshold)
        members = sorted(members, key=lambda i: (-median[c, i], i))
        rows.append([(int(i), c) for i in members])

    n_columns = max(1, max(len(row) for row in rows))
    panels = [row[j] if j < len(row) else None for row in rows for j in range(n_columns)]
    return n_clusters, n_columns, panels


def plot_pies(
    results: Results,
    data: Data,
    config: Config,
    model: str | None = None,
    run: str | None = None,
    verbose: bool = True
) -> None:
    """Plot cluster membership per object as a grid of pie charts, KDEs or histograms.

    Pie charts show the share of posterior samples in which an object belongs
    to each cluster. KDEs and histograms show the distribution of each
    cluster's membership across samples.

    Args:
        results: MCMC results containing cluster samples.
        data: Tuple of (objects, features, confounders).
        config: Combined plot and style configuration.
        model: sBayes model name, e.g., K1 (optional).
        run: Run id appended to the file names, e.g. '0' (optional).
        verbose: If true, print a progress message. Default is True.
    """
    if verbose:
        print("Plotting pies...")
    objects, features, confounders = data
    pies = config.experiment.plots.pies or PiesConfig()
    style = config.style.pies
    global_style = config.style.global_

    clusters = np.asarray(results.clusters, dtype=float)
    n_samples, n_clusters, n_objects = clusters.shape

    # Sum cluster assignments over samples — shape: (n_clusters, n_objects)
    samples_per_cluster = np.sum(clusters, axis=0)

    confounder = None
    if pies.confounder is not None:
        if pies.confounder not in confounders:
            raise ValueError(f"Unknown confounder '{pies.confounder}' in plots.pies.confounder. "
                             f"Available confounders: {list(confounders)}.")
        confounder = confounders[pies.confounder]

    # Resolve cluster colors — cached, guaranteed consistent across plots
    cluster_colors = get_cluster_colors(
        n_clusters=n_clusters,
        custom_colors=config.style.global_.cluster_colors or None,
    )
    highlight = style.highlight
    other_rgba = mcolors.to_rgba(highlight.other_color, alpha=highlight.other_alpha)

    def is_main(cluster: int, main_cluster: int) -> bool:
        return not highlight.enabled or cluster == main_cluster

    n_row, n_col, panels = panel_layout(clusters, pies, style.output.n_columns)

    # Create the figure
    width = style.output.width
    height = style.output.height
    fig, axs = plt.subplots(n_row, n_col, figsize=(width * n_col, height * n_row), squeeze=False)

    for ax, panel in zip(axs.ravel(), panels):
        ax.patch.set_alpha(0.0)
        if panel is None:
            ax.axis('off')
            continue
        l, main_cluster = panel

        label = break_label(str(objects.names[l]), style.label.max_label_length)
        index = str(objects.indices[l] + 1)
        group_label = None
        if confounder is not None:
            group_label = confounder_label(confounder, l, style.label.max_label_length)

        if pies.chart_type == "pie":
            # Build pie slices — one per cluster plus remainder
            per_object = samples_per_cluster[:, l]
            no_cluster = max(0.0, n_samples - per_object.sum())
            slices = per_object.tolist() + [no_cluster]
            slice_colors = [
                mcolors.to_rgba(cluster_colors[c]) if is_main(c, main_cluster) else other_rgba
                for c in range(n_clusters)
            ]
            no_cluster_alpha = highlight.other_alpha if highlight.enabled else 1.0
            slice_colors.append(mcolors.to_rgba(style.pie.no_cluster_color, alpha=no_cluster_alpha))

            ax.pie(slices, colors=slice_colors, radius=style.pie.radius)

            # Add object index and name, with the confounder group beneath
            ax.text(
                style.axes.index_x, style.axes.label_y, index,
                size=style.label.index_size, va='center', ha="right",
                transform=ax.transAxes,
            )
            ax.annotate(
                label, (style.axes.name_x, style.axes.label_y), xycoords='axes fraction',
                xytext=(0, 1 if group_label else 0), textcoords='offset points',
                size=style.label.name_size, va='bottom' if group_label else 'center', ha="left",
            )
            if group_label:
                ax.annotate(
                    group_label, (style.axes.name_x, style.axes.label_y), xycoords='axes fraction',
                    xytext=(0, -1), textcoords='offset points',
                    size=style.label.confounder_size, color=style.label.confounder_color,
                    va='top', ha="left",
                )

            ax.set_xlim((style.axes.x_min, style.axes.x_max))
            ax.set_ylim((style.axes.y_min, style.axes.y_max))
            ax.axis('off')
            continue

        # KDE or histogram of each cluster's membership across samples
        bins = np.linspace(0.0, 1.0, style.distribution.n_bins + 1)
        for c in range(n_clusters):
            main = is_main(c, main_cluster)
            color = cluster_colors[c] if main else highlight.other_color
            zorder = 2 if main else 1
            if pies.chart_type == "kde":
                kdeplot_with_mean(
                    clusters[:, c, l], ax=ax, color=color,
                    lw=1.2 if main else 1.0,
                    alpha=0.6 if main else highlight.other_fill_alpha,
                    clip=(0, 1), zorder=zorder,
                    line_alpha=None if main else highlight.other_alpha,
                )
            else:
                ax.hist(
                    clusters[:, c, l], bins=bins, density=True, color=color,
                    alpha=0.8 if main else highlight.other_alpha,
                    edgecolor='none', zorder=zorder,
                )

        ax.set_xlim((-0.01, 1.01))
        ax.set_ylim(bottom=0, top=style.distribution.y_max)
        ax.set_xticks([0.0, 0.5, 1.0])
        ax.set_ylabel('')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        if pies.chart_type == "histogram":
            ax.spines['bottom'].set_visible(False)

        ax.text(
            0.98, 0.98, f'{index}  {label}',
            transform=ax.transAxes, ha='right', va='top',
            fontsize=style.distribution.name_size, fontweight='bold',
        )
        if group_label:
            # Place the group label beneath the (possibly two-line) name
            name_height = (label.count('\n') + 1) * 1.2 * style.distribution.name_size
            ax.annotate(
                group_label, (0.98, 0.98), xycoords='axes fraction',
                xytext=(0, -name_height - 1), textcoords='offset points',
                ha='right', va='top',
                fontsize=style.distribution.confounder_size,
                color=style.label.confounder_color,
            )

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
        path_out / f'pie_plot_K{results.n_clusters}{run_suffix(run)}.{global_style.format}',
        bbox_inches='tight',
        dpi=global_style.resolution,
        format=global_style.format,
    )
    plt.close(fig)
