import arviz as az
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from sblot.config.config_io import Config, ModelResults
from sblot.core.utils import likelihood_to_arviz


def plot_loo(all_models: list[ModelResults],
             config: Config,
             verbose: bool = True) -> None:
    """""Plot PSIS-LOO model comparison across experiments and clusters with different k.

    For a single k value, generates a box plot comparing experiments.
    For multiple k values, generates a line plot showing ELPD-LOO vs. k.

    Args:
        all_models: List of ModelResults containing results with pointwise likelihoods.
        config: Combined plot and style configuration.
        verbose: If True, print a progress message. Default is True.
    """
    if verbose:
        print("Plotting PSIS-LOO model comparison...")
    style = config.style.loo
    global_ = config.style.global_

    records = []
    for model in all_models:
        if model.results.likelihood_pointwise is None:
            raise ValueError(
                f"No pointwise likelihood found for model '{model.name}'. "
                "Re-run sBayes or to generate results with the derived/likelihood group."
            )
        loo = az.loo(likelihood_to_arviz(model.results.likelihood_pointwise), var_name="y")
        records.append({
            "experiment": model.name,
            "k": model.results.n_clusters,
            "elpd_loo": loo.elpd_loo,
        })


    df = pd.DataFrame(records)
    fig, ax = plt.subplots(figsize=(style.output.width, style.output.height))

    if df["k"].nunique() == 1:
        df["label"] = df["experiment"] + " (k=" + df["k"].astype(str) + ")"
        sns.boxplot(data=df, x="label", y="elpd_loo",
                    color=style.box_color, ax=ax)
        ax.set_xlabel("Experiment")
    else:
        sns.lineplot(data=df, x="k", y="elpd_loo", hue="experiment",
                     lw=style.line_width,
                     linestyle=style.line_style, ax=ax)
        ax.set_xlabel("Number of clusters (k)")
        ax.legend(fontsize=8)

    ax.set_ylabel("ELPD LOO")

    plt.tight_layout(pad=0.5)

    path_out = config.experiment.results.path_out / 'loo'
    path_out.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path_out / f'loo.{global_.format}',
        bbox_inches='tight',
        dpi=global_.resolution,
        format=global_.format,
    )
    plt.close(fig)