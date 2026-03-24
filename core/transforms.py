import numpy as np

from numpy.typing import NDArray
import pandas as pd
from pathlib import Path
from core.utils import parse_cluster_columns, cluster_agreement, write_clusters
from scipy.optimize import linear_sum_assignment
from shutil import copyfile

# todo: Change once sBayes numpyro is launched
from sbayes.results import Results

def get_cluster_probability(cluster: NDArray) -> NDArray[float]:
    """Computes the mean assignment probability of each site to a cluster.

    For hard assignment, input is boolean and output is the posterior frequency
    (fraction of samples in which the site was assigned to the cluster).
    For soft assignment, input is float in [0, 1] and output is the mean
    assignment probability across samples.

    Args:
        cluster: Array of shape (n_samples, n_sites), either boolean (hard
                 assignment) or float in [0, 1] (soft assignment).
    Returns:
        Array of shape (n_sites,) with values in [0, 1].
    """
    return np.mean(np.asarray(cluster), axis=0)


def load_clusters(filename: str | Path) -> NDArray[int]:
    """Load cluster posterior from a text file.

    Each line in the file represents one MCMC sample, containing cluster
    assignments for all objects across all clusters.

    Args:
        filename: Path to the cluster assignments text file.
    Returns:
        Integer array of shape (n_samples, n_clusters, n_objects) with
        binary cluster assignments.
    """
    with open(filename, 'r') as clusters_file:
        clusters = [
            parse_cluster_columns(line.strip())
            for line in clusters_file
            if line.strip()  # skip empty lines
        ]
    return np.array(clusters, dtype=int)

def permute_parameters(results: Results, permutation: NDArray[int]) -> pd.DataFrame:
    """Permute cluster-specific parameters to match a new cluster ordering.

    After aligning cluster labels across runs, the parameter columns in the
    stats file need to be reordered to match the new cluster permutation.
    Operates on areal (cluster) effect columns and cluster size columns.

    Args:
        results: Results object containing the parameters DataFrame and
                 cluster names.
        permutation: Integer array of shape (n_clusters,) mapping old cluster
                     indices to new ones, as returned by `linear_sum_assignment`.
    Returns:
        DataFrame with cluster-specific columns permuted to match the new
        cluster ordering.
    """
    parameters: pd.DataFrame = results.parameters.copy()
    cluster_names = np.array(results.cluster_names)
    remap = {}

    # Remap areal effect columns to match the new cluster ordering
    for clust_i, clust_j in zip(cluster_names, cluster_names[permutation]):
        prefix_i = f"areal_{clust_i}_"
        prefix_j = f"areal_{clust_j}_"
        for k in parameters.columns:
            if k.startswith(prefix_i):
                remap[k] = parameters[prefix_j + k[len(prefix_i):]]

    # Remap cluster size columns to match the new cluster ordering
    for i, j in enumerate(permutation):
        remap[f"size_a{i}"] = parameters[f"size_a{j}"]

    for k_old, k_new in remap.items():
        parameters[k_old] = k_new

    return parameters

def align_posterior(
    cluster_paths: list[Path],
    stats_paths: list[Path],
    backup_dir: Path,
) -> None:
    """Aligns posterior samples across multiple MCMC runs.

    Resolves the label-switching problem by permuting cluster labels in each
    run to maximally agree with the first run, which is used as the reference.
    Original files are backed up to `backup_dir` before being overwritten.

    Args:
        cluster_paths: Paths to cluster files for one model size, one per run.
        stats_paths: Paths to stats files for one model size, one per run.
        backup_dir: Directory to store backups of original files.
    """
    print("Aligning posterior samples across runs...")

    # Load all results and compute mean cluster assignments
    results = []
    mean_clusters = []
    for cluster_path, stats_path in zip(cluster_paths, stats_paths):
        result = Results.from_csv_files(cluster_path, stats_path, burn_in=0)
        results.append(result)
        mean_clusters.append(np.mean(result.clusters, axis=1))

    # Align all runs to the first run as reference
    for i in range(1, len(results)):
        # Back up original files before overwriting
        copyfile(cluster_paths[i], backup_dir / cluster_paths[i].name)
        copyfile(stats_paths[i], backup_dir / stats_paths[i].name)

        # Find the permutation that maximises cluster agreement with the first run
        d = cluster_agreement(mean_clusters[0], mean_clusters[i])
        perm = linear_sum_assignment(d, maximize=True)[1]

        # Apply permutation and overwrite originals
        clusters_aligned = results[i].clusters[perm].transpose((1, 0, 2))
        params_aligned = permute_parameters(results[i], perm)

        write_clusters(cluster_paths[i], clusters_aligned)
        params_aligned.to_csv(stats_paths[i], index=False, sep="\t")


def rank_clusters_by_likelihood(likelihood_single_clusters: dict) -> NDArray[float]:
    """Rank clusters by mean log-likelihood in descending order.

    Args:
        likelihood_single_clusters: Dict mapping cluster names to arrays of
                                    log-likelihood values.
    Returns:
        Array of mean log-likelihoods sorted in descending order.
    """
    lh_per_cluster = np.array(list(likelihood_single_clusters.values()), dtype=float)
    to_rank = np.mean(lh_per_cluster, axis=1)
    return to_rank[np.argsort(-to_rank)]