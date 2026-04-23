import arviz as az
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from sblot.config.config_io import Config, ModelResults

def plot_loo(all_models: list[ModelResults], config: Config) -> None:
    """""Plot PSIS-LOO model comparison across experiments and clusters with different k.

    For a single k value, generates a box plot comparing experiments.
    For multiple k values, generates a line plot showing ELPD-LOO vs. k.

    Args:
        all_models: list of ModelResults containing the likelihoods.
        config: Combined plot and style configuration.
    """
    style = config.style.loo
    global_ = config.style.global_

    records = []
    for model in all_models:
        for run_id, likelihood in model.likelihoods:
            loo = az.loo(likelihood, var_name="y")
            records.append({
                "experiment": model.name,
                "k": model.k,
                "run": run_id,
                "elpd_loo": loo.elpd
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