import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from sblot.config.config_io import Config, ModelResults


def relative_eff(log_lik: np.ndarray) -> float:
    """Relative efficiency (ESS / n_draws) of the pointwise likelihood draws for PSIS-LOO.

    Follows R's loo::relative_eff: the ESS of exp(log_lik) is computed per observation
    from the (autocorrelated) MCMC draws and averaged, since arviz only accepts a scalar.

    Args:
        log_lik: pointwise log-likelihoods of shape (n_draws, n_objects).
    """
    # Subtract the per-observation max to avoid underflow; ESS is invariant to scaling.
    lik = np.exp(log_lik - log_lik.max(axis=0, keepdims=True))
    ess = az.ess(az.convert_to_dataset({"lik": lik[np.newaxis, :, :]}), method="mean")["lik"].values
    return float(np.nanmean(ess) / log_lik.shape[0])


def plot_loo(all_models: list[ModelResults],
             config: Config,
             verbose: bool = True) -> None:
    """""Plot PSIS-LOO model comparison across experiments and clusters with different k.

    For a single k value, generates a box plot comparing experiments.
    For multiple k values, generates a line plot showing ELPD-LOO vs. k.

    Args:
        all_models: list of ModelResults containing the likelihoods.
        config: Combined plot and style configuration.
        verbose: If True, print a progress message. Default is True.
    """
    if verbose:
        print("Plotting PSIS-LOO model comparison...")
    style = config.style.loo
    global_ = config.style.global_

    records = []
    for model in all_models:
        likelihood_pointwise = model.results.likelihood_pointwise
        if likelihood_pointwise is None:
            raise ValueError(
                f"Results for model '{model.name}' do not contain pointwise log-likelihoods "
                "(required for PSIS-LOO). Re-run sBayes with likelihood logging enabled."
            )
        idata = az.from_dict(log_likelihood={"y": likelihood_pointwise[np.newaxis, :, :]})
        loo = az.loo(idata, var_name="y", reff=relative_eff(likelihood_pointwise))
        records.append({
            "experiment": model.name,
            "k": model.results.n_clusters,
            "run": model.run,
            "elpd_loo": loo.elpd,
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