import math
import numpy as np
import seaborn as sns

from numpy.typing import NDArray
from matplotlib import pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from sbayes.results import Results
from sblot.config.config_io import Config
from sblot.core.render import kdeplot_with_mean, PREF_COLOR_MAP
from sblot.core.utils import get_corner_points, to_folder_name


def plot_preferences_simplex(
    samples: NDArray[float],
    feature: str,
    label_names: list[str],
    ax: plt.Axes,
    config: Config,
    reference_samples: NDArray[float] | None = None,
) -> None:
    """Plot a single preference distribution in a simplex representation.

    For binary features (2 states) plots a 1D KDE on [0,1].
    For features with more states plots a 2D KDE projected onto the simplex.

    Args:
        samples: Sampled preference vectors, shape (n_samples, n_states).
        feature: Name of the feature being plotted.
        label_names: State labels for the simplex corners.
        ax: Matplotlib axis to draw on.
        config: Combined plot and style configuration.
        reference_samples: Optional reference distribution shown as overlay.
    """
    # Filter out non-finite samples
    valid = np.all(np.isfinite(samples), axis=1)
    samples = samples[valid]
    n_samples, n_p = samples.shape

    style = config.style.preferences
    color = style.color
    reference_color = style.reference_color

    # Add feature name as title
    if style.legend.title.add:
        ax.text(
            style.legend.title.position.x,
            style.legend.title.position.y,
            str(feature),
            fontsize=style.legend.title.font_size,
            fontweight='bold',
            transform=ax.transAxes,
        )

    if n_p == 2:
        x = samples.T[1]
        kdeplot_with_mean(x, color=color, ax=ax, lw=1, clip=(0, 1), zorder=1, alpha=0.6)

        # Draw reference distribution if provided
        if reference_samples is not None:
            valid_ref = np.all(np.isfinite(reference_samples), axis=1)
            x_ref = reference_samples[valid_ref].T[1]
            kdeplot_with_mean(x_ref, color=reference_color, ax=ax, lw=1,
                              clip=(0, 1), zorder=0, alpha=0.6)

        ax.axes.get_yaxis().set_visible(False)

        # Add state labels
        if style.legend.labels.add:
            for i, label in enumerate(label_names):
                x_pos = 0.05 if i == 0 else 0.95
                ax.text(
                    x_pos, -0.05, label,
                    ha='center', va='top',
                    fontdict={'fontsize': style.legend.labels.font_size},
                    transform=ax.transAxes,
                )

        ax.plot([0, 1], [0, 0], lw=1, color=color, clip_on=False)
        ax.set_ylim(bottom=0)
        ax.set_xlim((-0.01, 1.01))
        ax.axis('off')

    elif n_p > 2:
        # Compute simplex corners
        corners = get_corner_points(n_p)
        xmin, ymin = np.min(corners, axis=0)
        xmax, ymax = np.max(corners, axis=0)

        # Project samples onto 2D simplex
        samples_projected = samples.dot(corners)
        x = samples_projected.T[0]
        y = samples_projected.T[1]

        # KDE density plot
        sns.kdeplot(
            x=x, y=y,
            fill=True, thresh=0, cut=30, levels=20,
            clip=((xmin, xmax), (ymin, ymax)),
            cmap=PREF_COLOR_MAP, ax=ax, zorder=1,
        )

        # Plot mean marker
        mean_projected = np.mean(samples, axis=0).dot(corners)
        ax.scatter(
            *mean_projected.T,
            color=color, lw=1, ec="#ffeeaa",
            s=50, marker="o", zorder=11,
        )

        # Plot reference mean if provided
        if reference_samples is not None:
            valid_ref = np.all(np.isfinite(reference_samples), axis=1)
            ref_mean_projected = np.mean(reference_samples[valid_ref], axis=0).dot(corners)
            ax.scatter(
                *ref_mean_projected.T,
                color=reference_color, lw=1, ec="#a0a0a0",
                s=40, marker="o", alpha=0.9, zorder=10,
            )

        # Clip all artists to simplex boundary
        clip_patch = MplPolygon(corners, closed=True, transform=ax.transData)
        for artist in ax.get_children():
            artist.set_clip_path(clip_patch)

        # Draw simplex outline on top
        ax.fill(*corners.T, edgecolor='k', facecolor='none', lw=1, zorder=10)

        # Add state labels
        if style.legend.labels.add:
            for xy, label in zip(corners, label_names):
                xy = xy * 1.2
                # Split long labels at midpoint
                if (" " in label or "-" in label) and len(label) > 10:
                    split_chars = [i for i, c in enumerate(label) if c in (" ", "-")]
                    mid = len(label) / 2
                    break_at = min(split_chars, key=lambda i: abs(i - mid))
                    label = label[:break_at] + "\n" + label[break_at:]
                ax.text(
                    float(xy[0]), float(xy[1]), str(label),
                    ha='center', va='center',
                    fontdict={'fontsize': style.legend.labels.font_size},
                )

        ax.set_xlim((xmin - 0.1, xmax + 0.1))
        ax.set_ylim((ymin - 0.1, ymax + 0.1 + 0.3))
        ax.axis('off')


def plot_preferences(
    results: Results,
    config: Config,
    model: str | None = None,
    verbose: bool = True
) -> None:
    """Plot preference distributions for all components in a grid.

    Creates one grid per component (areal effect and each confounder group),
    with one simplex panel per feature. Each grid is saved to a separate file.

    Args:
        results: MCMC results containing preference samples.
        config: Combined plot and style configuration.
        model: sBayes model name, e.g., K1 (optional).
        verbose: If True, print a progress message. Default is True.
    """
    if verbose:
        print("Plotting preferences...")

    experiment = config.experiment.plots.preferences
    style = config.style.preferences
    global_style = config.style.global_

    # Combine areal effect and confounding effects into one dict
    # structure: {component: {feature: state_probabilities}}
    preferences = {f'cluster_{k}': v for k, v in results.areal_effect.items()}

    for conf_name, conf_effect in results.confounding_effects.items():
        for group, preference in conf_effect.items():
            preferences[f'{conf_name}_{group}'] = preference

    # Resolve reference samples if a reference confounder is specified
    if experiment.reference is not None:
        groups = results.groups_by_confounders[experiment.reference]
        assert len(groups) == 1 and groups[0] == "<ALL>", \
            "Reference confounder must apply to all objects (<ALL>)."
        reference_samples = preferences[f"{experiment.reference}_<ALL>"]
    else:
        reference_samples = None

    # Filter to requested preference components
    if experiment.components:
        component_keys = []
        for c in experiment.components:
            if c.groups:
                groups = c.groups
            else:
                if c.component == "cluster":
                    groups = list(results.areal_effect.keys())
                elif c.component in results.confounders:
                    groups = results.groups_by_confounders[c.component]
                else:
                    raise ValueError(
                        f"'{c.component}' is not a valid component. "
                        f"Must be 'cluster' or one of: {list(results.confounders)}."
                    )
            component_keys.extend([f'{c.component}_{g}' for g in groups])

        preferences = {k: v for k, v in preferences.items()
                       if k in component_keys}

    # Filter to requested features within each component
    if experiment.features:
        preferences = {
            k: {f: v[f] for f in experiment.features if f in v}
            for k, v in preferences.items()
        }

    # Compute grid dimensions
    n_plots = len(next(iter(preferences.values())))
    n_col = style.output.n_columns
    n_row = math.ceil(n_plots / n_col)
    width = style.output.width_subplot
    height = style.output.height_subplot

    # Plot one grid per component
    for component, pref_by_feat in preferences.items():
        fig, axs = plt.subplots(
            n_row, n_col,
            figsize=(width * n_col, height * n_row),
        )
        axs_flat: list[plt.Axes] = fig.axes

        # Hide empty panels
        n_empty = n_row * n_col - n_plots
        for e in range(1, n_empty + 1):
            axs_flat[-e].axis('off')

        for position, (f, pref) in enumerate(pref_by_feat.items()):
            states = results.get_states_for_feature_name(f)

            # Don't show reference overlay for the reference component itself
            ref = (
                reference_samples[f]
                if reference_samples is not None
                and experiment.reference != component
                else None
            )

            plot_preferences_simplex(
                samples=pref,
                feature=f,
                label_names=states,
                ax=axs_flat[position],
                config=config,
                reference_samples=ref,
            )
            if verbose:
                print(f"{component}: {position + 1} of {n_plots} plots finished")

        plt.subplots_adjust(
            wspace=style.output.spacing_horizontal,
            hspace=style.output.spacing_vertical,
        )

        if model is not None:
            path_out = config.experiment.results.path_out / to_folder_name(model) / 'preferences'
        else:
            path_out = config.experiment.results.path_out / 'preferences'

        path_out.mkdir(parents=True, exist_ok=True)


        fig.savefig(
            path_out / f'preferences_{component}.{global_style.format}',
            bbox_inches='tight',
            dpi=global_style.resolution,
            format=global_style.format,
        )
        plt.close(fig)