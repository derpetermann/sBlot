import numpy as np

from numpy.typing import NDArray
import pandas as pd
from pathlib import Path
from sblot.core.utils import (parse_cluster_columns, cluster_agreement,
                              compute_delaunay, graph_from_delaunay)
from scipy.optimize import linear_sum_assignment
from sbayes.results import Results
from typing import Literal


def get_cluster_probability(cluster: NDArray) -> NDArray[float]:
    """Computes the mean assignment probability of each site to a cluster.

    For hard assignment, input is boolean and output is the fraction of samples
    in which the site was assigned to the cluster. For soft assignment, input is
    float in [0, 1] and output is the mean assignment probability across samples.

    Args:
        cluster: Array of shape (n_samples, n_objects), either boolean (hard
                 assignment) or float in [0, 1] (soft assignment).
    Returns:
        Array of shape (n_objects,) with values in [0, 1].
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
) -> list[Results]:
    """Align posterior samples across multiple MCMC runs.

    Resolves the label-switching problem by permuting cluster labels in each
    run to maximally agree with the first run, which is used as the reference.

    Args:
        cluster_paths: Paths to cluster files for one model size, one per run.
        stats_paths: Paths to stats files for one model size, one per run.
    Returns:
        List of Results objects with aligned cluster labels, one per run.
    """
    print("Aligning posterior samples across runs...")

    # Load all runs without burn-in for alignment
    all_results = [
        Results.from_csv_files(c, s, burn_in=0)
        for c, s in zip(cluster_paths, stats_paths)
    ]

    # Compute mean cluster assignments per run
    mean_clusters = [np.mean(r.clusters, axis=1) for r in all_results]

    # Align all runs to the first run as reference
    for i in range(1, len(all_results)):
        d = cluster_agreement(mean_clusters[0], mean_clusters[i])
        _, perm = linear_sum_assignment(-d)
        all_results[i].clusters = all_results[i].clusters[perm]
        all_results[i].parameters = permute_parameters(all_results[i], perm)

    return all_results


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


def clusters_to_graph(
        cluster: NDArray,
        locations_map_crs: NDArray[float],
        graph_type: Literal["complete", "delaunay", "gabriel"],
        min_posterior_prob: float | None,
) -> tuple[NDArray[bool], NDArray[float], NDArray[float]]:
    """Compute a graph of cluster connections from posterior samples.

    Args:
        cluster: Boolean or float array of shape (n_samples, n_objects).
        locations_map_crs: Site locations in map CRS, shape (n_objects, 2).
        graph_type: Type of graph to compute ("complete", "delaunay", or "gabriel")
        min_posterior_prob: Minimum posterior assignment probability of an object to a cluster to be included in the graph.

    Returns:
        Tuple of:
            - in_cluster: Boolean mask of sites in the cluster.
            - lines: Array of line endpoints, shape (n_edges, 2, 2).
            - line_weights: Posterior co-occurrence frequency per edge.
    """
    cluster = np.asarray(cluster)
    n_samples = cluster.shape[0]

    if min_posterior_prob is None:
        min_posterior_prob = 0.0

    # Compute posterior assignment probability per object
    prob_in_cluster = np.sum(cluster, axis=0) / n_samples
    in_graph = prob_in_cluster >= min_posterior_prob
    locations = locations_map_crs[in_graph]
    n_graph = len(locations)

    if n_graph > 3:
        if graph_type == "complete":
            a = np.arange(n_graph)
            b = np.array(np.meshgrid(a, a))
            c = b.T.reshape(-1, 2)
            graph_connections = c[c[:, 0] < c[:, 1]]
        elif graph_type == "delaunay":
            delaunay = compute_delaunay(locations)
            graph_connections = graph_from_delaunay(delaunay, locations, "delaunay")
        elif graph_type == "gabriel":
            delaunay = compute_delaunay(locations)
            graph_connections = graph_from_delaunay(delaunay, locations, "gabriel")
        else:
            raise NotImplementedError(f"Unknown graph type: '{graph_type}'. "
                                      f"Choose from 'complete', 'delaunay' or 'gabriel'.")

    elif n_graph == 3:
        graph_connections = np.array([[0, 1], [1, 2], [2, 0]], dtype=int)
    elif n_graph == 2:
        graph_connections = np.array([[0, 1]], dtype=int)
    else:
        return in_graph, np.array([]), np.array([])


    cluster_indices = np.argwhere(in_graph)
    starts = cluster_indices[graph_connections[:, 0]].ravel()
    ends = cluster_indices[graph_connections[:, 1]].ravel()

    lines = np.array([locations_map_crs[starts],
                      locations_map_crs[ends]]).transpose((1, 0, 2))
    line_weights = np.sum(np.minimum(cluster[:, starts], cluster[:, ends]), axis=0) / n_samples

    return in_graph, lines, line_weights
