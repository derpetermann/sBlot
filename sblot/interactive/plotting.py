from __future__ import annotations

import numpy as np
import pandas as pd

from sblot.core.utils import padded_range, compute_delaunay, graph_from_delaunay
from sblot.core.render import COLOR_NEUTRAL

from plotly import express as px, graph_objects as go
from sblot.core.utils import compute_balanced_geo_ranges
from sblot.interactive.app_state import AppState
from sblot.interactive.styles import blank_layout
from numpy.typing import NDArray


def initialize_results_map(state: AppState) -> go.Figure:
    """Initialize the results map figure and store it in the application state.

    Creates a geographic scatter plot of all objects colored by their cluster
    assignment, with one empty line trace per cluster for rendering Gabriel
    graph connections. Lines are placed behind scatter points by reversing
    the trace order.

    The figure and its component traces are stored directly on the state object
    so that later plot_summary_map and plot_sample_map calls can update
    them in place without recreating the full figure — which is necessary for
    Dash performance.

    Args:
        state: Current application state containing object data, locations
               and cluster colors. Modified in place to store fig, lines
               and scatter.
    Returns:
        The initialized Plotly figure.
    """
    # Create a scatter plot of all objects colored by cluster assignment
    fig = px.scatter_geo(
        state.object_data,
        lat="y",
        lon="x",
        color="cluster",
        hover_data=["name", state.confounder, "posterior_support", "cluster"],
        projection="equirectangular",
        color_discrete_sequence=state.cluster_colors,
    )

    # Add one empty line trace per cluster for Gabriel graph connections
    for i in range(state.n_clusters):
        fig_lines = px.line_geo(lat=[None], lon=[None])
        fig = go.Figure(fig.data + fig_lines.data)

    x_range, y_range = compute_balanced_geo_ranges(state.locations)
    fig.update_layout(
        height=600,
        margin=dict(l=0, r=0, b=0, t=0, pad=0),
        geo=dict(
            lonaxis=dict(
                showgrid=True,
                gridwidth=0.5,
                range=x_range,
                dtick=5,
            ),
            lataxis=dict(
                showgrid=True,
                gridwidth=0.5,
                range=y_range,
                dtick=5,
            ),
            projection_scale=1
        ),
    )

    # Store figure components in state for in-place updates
    state.fig = fig
    state.lines = fig.data[1:]
    state.scatter = fig.data[0] # type: ignore[assignment]

    # Reverse trace order so lines render behind scatter points
    fig.data = fig.data[::-1]

    return fig


def initialize_data_map(state: AppState) -> go.Figure:
    """Initialize the data map figure showing all objects without cluster assignments.

    Creates a geographic scatter plot of all objects with a neutral color,
    used in the Data tab before any cluster results have been loaded. The
    figure is stored in state.data_fig by the caller after this function
    returns.

    Args:
        state: Current application state containing object data and locations.
    Returns:
        The initialized Plotly figure.
    """
    fig = px.scatter_geo(
        state.object_data,
        lat="y",
        lon="x",
        hover_data=["name", state.confounder],
        projection="equirectangular",
        size_max=0.1,
    )

    fig.update_traces(marker=dict(size=4, color=COLOR_NEUTRAL))
    x_range, y_range = compute_balanced_geo_ranges(state.locations)

    fig.update_layout(
        height=600,
        margin=dict(l=0, r=0, b=0, t=0, pad=0),
        geo=dict(
            lonaxis=dict(
                showgrid=True,
                gridwidth=0.5,
                range=x_range,
                dtick=5,
            ),
            lataxis=dict(
                showgrid=True,
                gridwidth=0.5,
                range=y_range,
                dtick=5,
            ),
            projection_scale=1
        ),
    )
    return fig


def plot_trace(state: AppState, interval: int = 2) -> go.Figure:
    """Plot the cluster size trace showing how cluster assignments evolve over samples.

    For each cluster, plot the number of objects assigned to it at each
    posterior sample. Samples are thinned by `interval` for performance.
    Used in the Results tab to visually inspect MCMC mixing and convergence.

    Args:
        state: Current application state containing cluster samples and colors.
        interval: Thinning factor for samples — only every nth sample is
                  plotted. Higher values improve performance at the cost of
                  resolution. Default to 2.
    Returns:
        A Plotly line figure with one trace per cluster.
    """
    # Thin samples and compute cluster sizes — shape: (n_clusters, n_thinned_samples)
    sizes_np = np.sum(state.clusters[:, ::interval, :], axis=2)

    # Convert to long-form DataFrame for plotly express
    sizes_df = pd.DataFrame(
        [(i, interval * j, s) for (i, j), s in np.ndenumerate(sizes_np)],
        columns=["cluster", "sample", "size"],
    )

    fig = px.line(
        sizes_df,
        x="sample",
        y="size",
        color="cluster",
        color_discrete_sequence=state.cluster_colors,
    )
    fig.update_traces(line={"width": 1.0})
    fig.update_layout(
        height=160,
        margin=dict(l=20, r=20, t=0, b=10),
        **blank_layout,
    )

    return fig



def plot_summary_map(
    state: AppState,
    sample_range: list[int],
    posterior_threshold: float = 0.5,
) -> go.Figure:
    """Plot a summary map aggregating cluster assignments over a range of samples.

    For each object, computes the mean posterior probability of belonging to
    each cluster over the specified sample range. Objects are assigned to the
    cluster whose posterior probability exceeds `posterior_threshold`. Objects
    below the threshold for all clusters are assigned to no cluster (index -1).

    Updates the existing figure in state in place for Dash performance —
    avoids recreating the full figure on each callback.

    Args:
        state: Current application state containing clusters, locations and
               the figure. Modified in place.
        sample_range: [i_start, i_end] indices defining the range of posterior
                      samples to summarise.
        posterior_threshold: Minimum posterior probability for an object to be
                             assigned to a cluster. Default to 0.5.
    Returns:
        The updated Plotly figure stored in state.fig.
    """
    i_start, i_end = sample_range

    # Compute mean posterior probability per cluster per object
    # shape: (n_clusters, n_objects)
    cluster_posterior = np.mean(state.clusters[:, i_start:i_end, :], axis=1)
    summary_clusters = cluster_posterior > posterior_threshold

    # Assign objects to clusters or mark as unassigned
    state.object_data.posterior_support = 1 - np.sum(cluster_posterior, axis=0)
    any_cluster = np.any(summary_clusters, axis=0)
    state.object_data.loc[any_cluster, "cluster"] = np.nonzero(summary_clusters.T)[1]
    state.object_data.loc[~any_cluster, "cluster"] = -1

    # Update Gabriel graph lines and hover data per cluster
    for i, c in enumerate(summary_clusters):
        state.lines[i].lon, state.lines[i].lat = cluster_to_graph(state.locations[c])
        state.lines[i].line.color = state.cluster_colors[i]
        state.scatter.customdata[c, 2] = i
        state.scatter.customdata[c, 3] = cluster_posterior[i, c]


    state.scatter.hovertemplate = (
        "y=%{lat}<br>x=%{lon}<br>"
        "name=%{customdata[0]}<br>"
        "group=%{customdata[1]}<br>"
        "cluster=%{customdata[2]}<br>"
        "posterior_support=%{customdata[3]:.2f}"
    )

    # Update marker colors and sizes — enlarge highlighted cluster if set
    marker_style = {
        "color": state.cluster_colors[state.object_data["cluster"].to_numpy()]
    }
    if state.highlighted_cluster is None:
        marker_style["size"] = np.full(state.n_objects, 4)
    else:
        in_cluster = state.object_data.cluster == state.highlighted_cluster
        marker_style["size"] = np.where(in_cluster, 10, 4)

    state.fig.update_traces(marker=marker_style)
    return state.fig


def plot_sample_map(state: AppState, i_sample: int) -> go.Figure:
    """Plot a map of cluster assignments for a single posterior sample.

    Assigns each object to the cluster it belongs to in sample `i_sample`,
    or marks it as unassigned (index -1) if it is not in any cluster.
    Updates Gabriel graph lines and marker colors accordingly.

    Updates the existing figure in state in place for Dash performance —
    avoids recreating the full figure on each callback.

    Args:
        state: Current application state containing clusters, locations and the
               figure. Modified in place.
        i_sample: Index of the posterior sample to display.
    Returns:
        The updated Plotly figure stored in state.fig.
    """
    # Assign objects to clusters or mark as unassigned
    any_cluster = np.any(state.clusters[:, i_sample], axis=0)
    state.object_data.loc[any_cluster, "cluster"] = (
        np.nonzero(state.clusters[:, i_sample].T)[1]
    )
    state.object_data.loc[~any_cluster, "cluster"] = -1
    state.scatter.customdata[~any_cluster, 2] = ""

    # Update Gabriel graph lines and hover data per cluster
    for i, c in enumerate(state.clusters[:, i_sample, :]):
        state.lines[i].lon, state.lines[i].lat = cluster_to_graph(state.locations[c])
        state.lines[i].line.color = state.cluster_colors[i]
        state.scatter.customdata[c, 2] = i

    state.scatter.hovertemplate = (
        "y=%{lat}<br>x=%{lon}<br>"
        "name=%{customdata[0]}<br>"
        "group=%{customdata[1]}<br>"
        "cluster=%{customdata[2]}"
    )

    # Update marker colors and sizes — enlarge highlighted cluster if set
    marker_style = {
        "color": state.cluster_colors[state.object_data["cluster"].to_numpy()]
    }
    if state.highlighted_cluster is None:
        marker_style["size"] = np.full(state.n_objects, 4)
    else:
        in_cluster = state.object_data.cluster == state.highlighted_cluster
        marker_style["size"] = np.where(in_cluster, 10, 4)

    state.fig.update_traces(marker=marker_style)
    return state.fig


def cluster_to_graph(
    locations: NDArray[float],
) -> tuple[list[float], list[float]]:
    """Compute a Gabriel graph for a cluster and return as Plotly line coordinates.

    Wraps the core Gabriel graph computation and converts the output to
    the coordinate list format required by Plotly's line_geo traces, where
    segments are separated by None values.

    Args:
        locations: Array of shape (n_objects, 2) with x, y coordinates of
                   objects in the cluster.
    Returns:
        Tuple of (x, y) coordinate lists with None separating line segments,
        ready for use in a Plotly line_geo trace. Returns ([], []) if fewer
        than two objects are in the cluster.
    """
    if len(locations) < 2:
        return [], []

    delaunay = compute_delaunay(locations)
    graph_connections = graph_from_delaunay(delaunay, locations, "gabriel")

    x, y = [], []
    for i1, i2 in graph_connections:
        x += [locations[i1, 0], locations[i2, 0], None]
        y += [locations[i1, 1], locations[i2, 1], None]

    return x, y
