import geopandas as gpd
import importlib.resources as resources
import logging
import numpy as np
import pandas as pd
import warnings

from antimeridian import fix_polygon, fix_multi_polygon, FixWindingWarning
from itertools import compress
from math import ceil
from matplotlib import pyplot as plt, colors
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox

from matplotlib.patches import Patch, Rectangle, Wedge
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from numba.core.types import Literal
from numpy.typing import NDArray
from sbayes.results import Results
from sbayes.load_data import Data, Objects
from sblot.config.config_io import Config
from sblot.core.render import style_axes, make_likelihood_legend, annotate_label
from sblot.core.utils import (reproject_locations, compute_extent, Extent,
                              get_cluster_colors, lighten_color, compute_alpha_shape, compute_idw_grid,
                              to_folder_name)
from sblot.core.transforms import get_cluster_probability, clusters_to_graph
from shapely import BufferCapStyle, BufferJoinStyle, unary_union, Point
from shapely.geometry import Polygon, box
from shapely.plotting import plot_polygon
from typing import Literal


def add_basemap_polygon(
    config: Config,
    bbox: Polygon,
    ax: plt.Axes,
    z_order: int = -100000,
) -> gpd.GeoDataFrame:
    """Add polygon layer to the map axis as a background.

    Loads either the package default land polygons or a user-provided
    polygon GeoJSON file. Clips to the bounding box and reprojects to the map CRS.
    Handles anti-meridian wrapping for projections with non-zero false origin.

    Args:
        config: Combined plot and style configuration.
        bbox: Bounding box polygon for clipping in map CRS.
        ax: Matplotlib axis to draw on.
        z_order: Drawing order
    Returns:
        GeoDataFrame of the plotted world polygons.
    """
    geo = config.style.map.geo
    graphics = config.style.map.graphics
    map_proj = geo.resolve_projection(config.experiment.data.projection)

    # Load the polygon file. Use package default or user-provided path
    if geo.basemap.polygon == '<DEFAULT>':
        ref = resources.files('sblot.data.map') / 'land.geojson'
        with resources.as_file(ref) as geojson_path:
             polygons = gpd.read_file(geojson_path)

    else:
        polygons = gpd.read_file(geo.basemap.polygon)

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=FixWindingWarning)
        polygons.geometry = polygons.geometry.apply(
            lambda geom: fix_polygon(geom) if geom.geom_type == 'Polygon'
            else fix_multi_polygon(geom)
        )

    polygons = polygons.to_crs(map_proj)
    polygons.geometry = polygons.geometry.buffer(0)
    polygons = gpd.clip(polygons, bbox)

    polygons.plot(
        ax=ax,
        facecolor=graphics.basemap.polygon.color,
        edgecolor=graphics.basemap.polygon.outline_color,
        lw=graphics.basemap.polygon.outline_width,
        zorder=z_order,
    )
    return polygons


def add_basemap_line(
    config: Config,
    bbox: Polygon,
    ax: plt.Axes,
    z_order: int = -10000,
) -> None:
    """Add GeoJSON line layer (rivers, lakes) to the map axis.

    Loads either the package default river/lake geometries or a
    user-provided GeoJSON file. Clips to the bounding box and
    reprojects to the map CRS.

    Args:
        config: Combined plot and style configuration.
        bbox: Bounding box polygon for clipping in map CRS.
        ax: Matplotlib axis to draw on.
        z_order: Drawing order.
    """
    geo = config.style.map.geo
    graphics = config.style.map.graphics
    map_proj = geo.resolve_projection(config.experiment.data.projection)

    # Load line file — use package default or user-provided path
    if geo.basemap.line == '<DEFAULT>':
        ref = resources.files('sblot.data.map') / 'rivers_lakes.geojson'
        with resources.as_file(ref) as geojson_path:
            lines = gpd.read_file(geojson_path)
    else:
        lines = gpd.read_file(geo.basemap.line)

    lines = lines.to_crs(map_proj)
    lines = gpd.clip(lines, bbox)

    lines.plot(
        ax=ax,
        color=graphics.basemap.line.color,
        lw=graphics.basemap.line.width,
        zorder=z_order,
    )


def add_basemap_point(
    config: Config,
    bbox: Polygon,
    ax: plt.Axes,
    z_order: int = -8000,
) -> None:
    """Add GeoJSON point layer to the map axis.

    Only renders if a point file path is configured. Unlike polygons and
     lines, there is no package default — users must provide a path.

    Args:
        config: Combined plot and style configuration.
        bbox: Bounding box polygon for clipping in map CRS.
        ax: Matplotlib axis to draw on.
        z_order: Drawing order.
    """
    geo = config.style.map.geo
    graphics = config.style.map.graphics

    if not geo.base_map.geojson_points:
        return

    points = gpd.read_file(geo.base_map.geojson_points)
    points = points.to_crs(geo.map_projection)
    points = gpd.clip(points, bbox)

    points.plot(
        ax=ax,
        color=graphics.base_map.point_style.color,
        markersize=graphics.base_map.point_style.size,
        marker=graphics.base_map.point_style.marker,
        zorder=z_order,
    )

def visualise_basemap(
    extent: Extent,
    config: Config,
    ax: plt.Axes,
) -> None:
    """Add base map polygon, line and point layers to the map axis.

    Adds layers if the corresponding file paths are configured.
    Silently skips missing optional layers.

    Args:
        extent: Spatial extent dict with x_min, x_max, y_min, y_max.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    """
    basemap = config.style.map.geo.basemap

    if not basemap.add:
        return

    bbox = extent.to_bbox()

    if basemap.polygon:
        add_basemap_polygon(config, bbox, ax)
    else:
        print('Cannot add base map polygon. Please provide a geojson_polygon path.')

    if basemap.line:
        add_basemap_line(config, bbox, ax)

    if basemap.point:
        add_basemap_point(config, bbox, ax)


def get_cluster_graph(
    clusters: NDArray[bool],
    locations_map_crs: NDArray[float],
    config: Config,
) -> list[tuple[NDArray[bool], NDArray[float], NDArray[float]]]:
    """Compute graphs for all clusters.

    Args:
        clusters: Cluster samples.
        locations_map_crs: Object locations in map CRS.
        config: Combined plot and style configuration.
    Returns:
        List of (in_cluster, lines, line_weights) tuples per cluster.
    """
    experiment = config.experiment.plots.map
    return [
        clusters_to_graph(
            np.asarray(c),
            locations_map_crs,
            experiment.line.graph,
            experiment.min_posterior_probability,
        )
        for c in clusters
    ]


def draw_cluster_lines(
    graphs: list[tuple[NDArray[bool], NDArray[float], NDArray[float]]],
    cluster_colors: list[str],
    config: Config,
    ax: plt.Axes,
) -> list:
    """Draw cluster connection lines and return legend handles.

    Args:
        graphs: List of (in_cluster, lines, line_weights) tuples per cluster.
        cluster_colors: Colors for each cluster.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    Returns:
        List of legend handles, one per cluster.
    """
    graphics = config.style.map.graphics
    legend_handles = []

    for c, (in_cluster, lines, line_weights) in enumerate(graphs):
        current_color = cluster_colors[c]

        for li, line in enumerate(lines):
            line_width = (
                graphics.clusters.max_line_width * line_weights[li]
                if graphics.clusters.line_width == "frequency"
                else graphics.clusters.line_width
            )
            alpha = (
                float(line_weights[li])
                if graphics.clusters.alpha == "frequency"
                else graphics.clusters.alpha
            )
            ax.plot(*np.asarray(line).T, color=current_color,
                    lw=line_width, alpha=alpha)

        legend_handles.append(
            Line2D([0, 100], [0, 0], color=current_color,
                   lw=graphics.clusters.max_line_width, linestyle='-')
        )

    return legend_handles


def render_cluster_connection(
    clusters: NDArray[bool],
    locations_map_crs: NDArray[float],
    cluster_colors: list[str],
    objects: Objects,
    config: Config,
    ax: plt.Axes,
) -> tuple[list[list[int]], list]:
    """Draw cluster connection lines and return legend handles.

    Args:
        clusters: Cluster samples.
        locations_map_crs: Object locations in map CRS.
        cluster_colors: Colors for each cluster.
        objects: Objects container with indices.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    Returns:
        Tuple of (cluster_labels, legend_handles)"""

    graphs = get_cluster_graph(clusters, locations_map_crs, config)
    legend_handles = draw_cluster_lines(graphs, cluster_colors, config, ax)
    cluster_labels = [list(compress(objects.indices, in_cluster)) for in_cluster, _, _ in graphs]
    return cluster_labels, legend_handles


def get_dominant_cluster(
    clusters: NDArray[bool],
    config: Config,
) -> NDArray[bool]:
    """For each object, find the cluster with the highest posterior assignment
    probability and determine whether it exceeds the minimum threshold.

    Args:
        clusters: Cluster samples.
        config: Combined plot and style configuration.
    Returns:
        Boolean mask — True if max_prob exceeds
        min_posterior_probability threshold, shape (n_clusters, n_objects).
    """
    map_config = config.experiment.plots.map

    # Compute posterior assignment probability per cluster
    # shape: (n_clusters, n_objects)
    cluster_assignment_prob = np.array([get_cluster_probability(c) for c in clusters])

    # Find the dominant cluster and its color
    dominant_cluster_idx = np.argmax(cluster_assignment_prob, axis=0)
    in_cluster = np.zeros_like(cluster_assignment_prob, dtype=bool)
    in_cluster[dominant_cluster_idx, np.arange(cluster_assignment_prob.shape[1])] = True

    if map_config.min_posterior_probability is not None:
        in_cluster &= cluster_assignment_prob >= map_config.min_posterior_probability

    return in_cluster




def add_overview_map(
    locations_map_crs: NDArray[float],
    extent: Extent,
    config: Config,
    ax: plt.Axes,
) -> None:
    """Add an inset overview map showing the broader geographic context.

    Args:
        locations_map_crs: Object locations in map CRS, shape (n_objects, 2).
        extent: Spatial extent of the main map.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    """
    legend = config.style.map.legend
    graphics = config.style.map.graphics

    if not legend.overview_map.add:
        return

    axins = inset_axes(
        ax,
        width=f"{legend.overview_map.width * 100}%",
        height=f"{legend.overview_map.height * 100}%",
        bbox_to_anchor=(legend.overview_map.position.x,
                        legend.overview_map.position.y,
                        1, 1),
        loc='lower left',
        bbox_transform=ax.transAxes,
    )
    axins.tick_params(labelleft=False, labelbottom=False, length=0)

    # Compute the overview extent by scaling the main map extent
    x_center = (extent.x_min + extent.x_max) / 2
    y_center = (extent.y_min + extent.y_max) / 2
    x_half = (extent.x_max - extent.x_min) / 2 * legend.overview_map.extent_factor.x
    y_half = (extent.y_max - extent.y_min) / 2 * legend.overview_map.extent_factor.y

    x_min = x_center - x_half
    x_max = x_center + x_half
    y_min = y_center - y_half
    y_max = y_center + y_half

    axins.set_xlim([x_min, x_max])
    axins.set_ylim([y_min, y_max])

    # Add a base map to overview
    overview_bbox = box(
        minx=x_min, miny=y_min, maxx=x_max, maxy=y_max
    )
    add_basemap_polygon(config, overview_bbox, axins)

    # Add site locations
    axins.scatter(
        *locations_map_crs.T,
        s=graphics.objects.size,
        color=graphics.objects.color,
        linewidth=0,
    )

    # Add bounding box showing the main map extent
    bbox_width = extent.x_max - extent.x_min
    bbox_height = extent.y_max - extent.y_min
    rect = Rectangle(
        (extent.x_min, extent.y_min),
        bbox_width, bbox_height,
        ec='k', fill=False, linestyle='-',
    )
    axins.add_patch(rect)


def add_cluster_legend(
    legend_handles: list,
    legend_labels: list[str],
    config: Config,
    ax: plt.Axes,
) -> None:
    """Add cluster legend to the map axis.

    Args:
        legend_handles: List of legend line handles.
        legend_labels: List of legend label strings.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    """
    legend = config.style.map.legend

    if not legend.clusters.add:
        return

    legend = ax.legend(
        legend_handles,
        legend_labels,
        title='Clusters',
        title_fontsize=legend.clusters.font_size + 4,
        frameon=True,
        edgecolor='#ffffff',
        framealpha=1,
        fontsize=legend.clusters.font_size,
        ncol=1,
        facecolor='#ffffff',
        columnspacing=1,
        loc='upper left',
        bbox_to_anchor=(legend.clusters.position.x,
                        legend.clusters.position.y),
    )
    # noinspection all
    legend._legend_box.align = "left" # type: ignore[union-attr]
    ax.add_artist(legend)


def add_labels(
    locations_map_crs: NDArray[float],
    cluster_labels: list[list[int]],
    cluster_colors: list[str],
    extent: Extent,
    config: Config,
    ax: plt.Axes
) -> None:
    """Add numeric labels to objects on the map.

    Args:
        locations_map_crs: objects locations in map CRS, shape (n_sites, 2).
        cluster_labels: List of object indices per cluster.
        cluster_colors: Colors for each cluster.
        extent: Spatial extent of the map.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    """
    experiment = config.experiment.plots.map
    graphics = config.style.map.graphics

    offset_x = (extent.x_max - extent.x_min) / 200
    offset_y = (extent.y_max - extent.y_min) / 200

    for i in range(locations_map_crs.shape[0]):
        label_color = "black"
        in_cluster = False

        for j, labels in enumerate(cluster_labels):
            if i in labels:
                if experiment.type == 'consensus_map':
                    label_color = cluster_colors[j]
                in_cluster = True

        if experiment.labels == 'in_cluster' and not in_cluster:
            continue

        annotate_label(
            xy=locations_map_crs[i],
            label=i + 1,
            color=label_color,
            offset_x=offset_x,
            offset_y=offset_y,
            ax=ax,
            fontsize=graphics.objects.font_size,
        )

def add_confounder_shapes(
    confounder: str,
    groups: NDArray[bool],
    group_names: list[str],
    locations_map_crs: NDArray[float],
    config: Config,
    ax: plt.Axes,
) -> None:
    """Add color overlays for a confounder to the map.

    For each group of one confounder adds a colored alpha
    shape (concave hull) around members with more than 3 locations.

    Args:
        confounder: Confounder name.
        groups: Boolean array of shape (n_groups, n_objects). Determines group membership.
        group_names: Names of each group.
        locations_map_crs: Object locations in map CRS, shape (n_objects, 2).
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    """

    graphics = config.style.map.graphics
    legend = config.style.map.legend

    cm = plt.get_cmap('gist_rainbow')
    group_colors = graphics.confounders.color
    # Resolve group colors
    if not group_colors:
        group_colors = [lighten_color(c[:3]) for c in
                        cm(np.linspace(0.0, 0.8, len(groups)))]
    elif len(group_colors) < len(groups):
        provided = [colors.to_rgba(c) for c in group_colors]
        additional = cm(np.linspace(0, 0.8,
                                    len(groups) - len(group_colors)))
        group_colors = provided + [lighten_color(c[:3]) for c in additional]
    else:
        group_colors = list(group_colors)

    handles = []
    for i, group in enumerate(group_names):
        group_color = group_colors[i]
        is_in_group = groups[i] == 1
        group_locations = locations_map_crs[is_in_group, :]

        # Scatter overlay for group members
        ax.scatter(
            *group_locations.T,
            s=graphics.confounders.size,
            color=group_color,
            linewidth=0,
            zorder=-i,
            label=group,
        )

        # Alpha shape for grups with more than 3 members
        if np.count_nonzero(is_in_group) > 3:
            try:
                alpha_shape = compute_alpha_shape(
                    points=group_locations,
                    alpha=graphics.confounders.shape,
                )
                if not alpha_shape.is_empty:
                    smooth_shape = alpha_shape.buffer(
                        graphics.confounders.buffer,
                        resolution=16,
                        cap_style=BufferCapStyle.round,
                        join_style=BufferJoinStyle.round,
                        mitre_limit=5.0,
                    )
                    plot_polygon(
                        smooth_shape,
                        ax=ax,
                        facecolor=group_color,
                        edgecolor=group_color,
                        lw=1,
                        add_points=False,
                        zorder=-i,
                    )

            except ZeroDivisionError:
                logging.warning(
                    f"Alpha shape for group '{group}' not plotted due to coincident locations. "
                    f"Set shape != 0 to avoid this."
                )

        handles.append(Patch(
            facecolor=group_color,
            edgecolor=group_color,
            label=group,
        ))

    # Add confounder legend
    if legend.confounders.add:
        legend = ax.legend(
            handles=handles,
            title=confounder.capitalize(),
            title_fontsize=legend.confounders.font_size + 4,
            fontsize=legend.confounders.font_size,
            frameon=True,
            edgecolor='#ffffff',
            framealpha=1,
            ncol=1,
            columnspacing=1,
            loc='upper left',
            bbox_to_anchor=(legend.confounders.position.x,
                            legend.confounders.position.y),
        )
        ax.add_artist(legend)
        # noinspection all
        legend._legend_box.align = "left"  # type: ignore[union-attr]


def add_lines_legend(config: Config, ax: plt.Axes) -> None:
    """Add lines width legend showing scale of posterior assignment probability.

    Args:
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    """
    legend = config.style.map.legend
    graphics = config.style.map.graphics

    if config.experiment.plots.map.type != "line" or not legend.lines.add:
        return

    line_widths = sorted(legend.lines.reference_frequencies, reverse=True)
    handles = []
    labels = []

    for w in line_widths:
        handles.append(Line2D([0], [0], color="black", linestyle='-',
                              lw=graphics.clusters.max_line_width * w))
        labels.append(f'{w:.0%}')

    legend = ax.legend(
        handles, labels,
        title_fontsize=legend.lines.font_size + 4,
        title='Frequency of edge in posterior',
        frameon=True,
        edgecolor='#ffffff',
        facecolor='#ffffff',
        framealpha=1,
        fontsize=legend.lines.font_size,
        ncol=1,
        columnspacing=1,
        loc='upper left',
        bbox_to_anchor=(legend.lines.position.x,
                        legend.lines.position.y),
    )
    # noinspection all
    legend._legend_box.align = "left"  # type: ignore[union-attr]
    ax.add_artist(legend)


def add_index_table(
    objects: Objects,
    cluster_labels: list[list[int]],
    cluster_colors: list[str],
    config: Config,
    ax: plt.Axes,
) -> None:
    """Add an index table mapping numbers to object names.

    Creates a table below the map showing which number corresponds to
    which object name, colored by cluster membership.

    Args:
        objects: Objects container with names and indices.
        cluster_labels: List of object indices per cluster.
        cluster_colors: Colors for each cluster.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
    """
    legend = config.style.map.legend

    objects_id = []
    objects_name = []
    objects_color = []

    for obj_id, obj_name in zip(objects.indices, objects.names):
        label_added = False
        for s, labels in enumerate(cluster_labels):
            if obj_id in labels:
                objects_id.append(obj_id)
                objects_name.append(obj_name)
                objects_color.append(cluster_colors[s])
                label_added = True

        if not label_added and legend.index_table.show == "all":
            objects_id.append(obj_id)
            objects_name.append(obj_name)
            objects_color.append("black")

    n_col = legend.index_table.n_columns
    n_row = ceil(len(objects_name) / n_col)

    table_fill = [[] for _ in range(n_row)]
    color_fill = [[] for _ in range(n_row)]

    for i, (object_id, object_name, object_color) in enumerate(
            zip(objects_id, objects_name, objects_color)):
        col = i % n_row
        table_fill[col].extend([str(object_id + 1), object_name])
        color_fill[col].extend([object_color, object_color])

    # Pad incomplete rows
    for row in table_fill:
        while len(row) < n_col * 2:
            row.append("")

    for row in color_fill:
        while len(row) < n_col * 2:
            row.append("#000000")

    widths = [0.025, 0.2] * n_col
    y_min = -(legend.index_table.height + 0.01)
    table = ax.table(
        cellText=table_fill,
        cellLoc="left",
        colWidths=widths,
        bbox=Bbox([[0.01, y_min], [0.99, y_min + legend.index_table.height]])) # type: ignore[call-arg]
    table.auto_set_font_size(False)
    table.set_fontsize(legend.index_table.font_size)
    table.scale(1, 2)

    if legend.index_table.color_labels:
        for i in range(n_row):
            for j in range(2 * n_col):
                table[(i, j)].get_text().set_color(color_fill[i][j])

    for cell in table.get_celld().values():
        cell.set_linewidth(0)


def render_line_map(
    results: Results,
    objects: Objects,
    locations_map_crs: NDArray[float],
    config: Config,
    ax: plt.Axes,
    single_cluster_id: int | None = None,
) -> tuple[list[list[int]], list[str]]:
    """Render a line map showing posterior cluster frequencies.

    Each site is drawn as a scatter point sized and colored by its maximum
    posterior frequency across all clusters. Cluster connections are drawn
    as lines weighted by their co-occurrence frequency in the posterior.

    Args:
        results: MCMC results containing cluster samples.
        objects: Objects container with site indices.
        locations_map_crs: Object locations in map CRS, shape (n_objects, 2).
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
        single_cluster_id: ID of a single cluster. If provided, plot a single cluster instead of all clusters. Defaults to None.

    Returns:
        Tuple of (cluster_labels, cluster_colors) where cluster_labels is
        a list of site index lists per cluster and cluster_colors is a list
        of hex color strings.
    """
    graphics = config.style.map.graphics
    legend = config.style.map.legend
    global_ = config.style.global_
    n_clusters = results.n_clusters

    cluster_colors = get_cluster_colors(
        n_clusters=n_clusters,
        custom_colors=global_.cluster_colors or None,
    )

    if single_cluster_id is not None:
        clusters = results.clusters[single_cluster_id:single_cluster_id + 1]
        cluster_colors = cluster_colors[single_cluster_id:single_cluster_id + 1]
    else:
        clusters = results.clusters

    # Get per-object cluster with max posterior assignment probability and its color
    in_cluster = get_dominant_cluster(clusters, config)

    cluster_prob_matrix = np.array([get_cluster_probability(c) for c in clusters])
    max_cluster_prob = cluster_prob_matrix[in_cluster]

    in_any_cluster = np.any(in_cluster, axis=0)
    max_cluster_color = np.array(cluster_colors)[np.argmax(in_cluster, axis=0)][in_any_cluster]

    # Scale point size by posterior frequency if requested
    if graphics.clusters.size == "frequency":
        point_size = max_cluster_prob * graphics.clusters.max_size
    else:
        point_size = graphics.clusters.size

    cluster_objects = locations_map_crs[in_any_cluster]

    ax.scatter(*cluster_objects.T,
               s=point_size, color=max_cluster_color)

    # Draw cluster connection lines and collect labels
    cluster_labels, legend_handles = render_cluster_connection(
        clusters, locations_map_crs, cluster_colors, objects, config, ax
    )

    # Build legend labels
    if legend.clusters.log_likelihood and single_cluster_id is None:
        legend_labels, legend_handles = make_likelihood_legend(
            results.likelihood_single_clusters
        )
    else:
        if single_cluster_id is not None:
            legend_labels =  [f'$Z_{{{single_cluster_id + 1}}}$']
        else:
            legend_labels = [f'$Z_{{{i + 1}}}$' for i in range(n_clusters)]

    add_cluster_legend(
        legend_handles, legend_labels, config, ax
    )

    return cluster_labels, cluster_colors


def render_pie_map(
    results: Results,
    objects: Objects,
    locations_map_crs: NDArray[float],
    config: Config,
    ax: plt.Axes,
    single_cluster_id: int | None = None,
) -> tuple[list[list[int]] | None, list[str]]:
    """Render a map with pie charts at each site showing cluster membership.

    Args:
        results: MCMC results containing cluster samples.
        objects: Objects container with site indices.
        locations_map_crs: Site locations in map CRS, shape (n_sites, 2).
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
        single_cluster_id: ID of a single cluster. If provided, plot a single cluster instead of all clusters. Defaults to None.

    Returns:
        Tuple of (cluster_labels | None, cluster_colors).
    """
    graphics = config.style.map.graphics
    legend = config.style.map.legend
    n_clusters = results.n_clusters

    cluster_colors = get_cluster_colors(
        n_clusters=n_clusters,
        custom_colors=config.style.global_.cluster_colors or None,
    )

    if single_cluster_id is not None:
        clusters = results.clusters[single_cluster_id:single_cluster_id + 1]
        cluster_colors = cluster_colors[single_cluster_id:single_cluster_id + 1]
    else:
        clusters = results.clusters

    in_cluster = get_dominant_cluster(clusters, config)
    cluster_prob_matrix = np.array([get_cluster_probability(c) for c in clusters])
    objects_in_cluster_indices = np.where(np.any(in_cluster, axis=0))[0]

    # Compute fixed pie radius in data units
    x_span = np.ptp(locations_map_crs[:, 0])
    y_span = np.ptp(locations_map_crs[:, 1])
    point_size = graphics.clusters.pie_radius_factor * min(x_span, y_span)

    # Draw pie chart at each object location
    for k, idx in enumerate(objects_in_cluster_indices):
        vals = np.clip(cluster_prob_matrix[:, idx].astype(float), 0.0, 1.0)
        remainder = max(0.0, 1.0 - float(vals.sum()))
        vals_full = list(vals) + [remainder]
        cols_full = list(cluster_colors) + ['lightgrey']

        start = 0.0
        for v, col in zip(vals_full, cols_full):
            if v <= 0.0:
                continue
            ax.add_patch(Wedge(
                center=(float(locations_map_crs[idx, 0]),
                        float(locations_map_crs[idx, 1])),
                r=point_size,
                theta1=float(start * 360.0),
                theta2=float((start + v) * 360.0),
                facecolor=col,
                edgecolor='black',
                linewidth=0.2,
                zorder=10,
            ))
            start += v

    if legend.clusters.add:
        # Build legend — one circle per cluster plus no-cluster
        legend_handles = [
            Line2D([0], [0], marker='o', color='w',
                   markerfacecolor=col, markeredgecolor='black',
                   markeredgewidth=0.5, markersize=10)
            for col in cluster_colors
        ] + [
            Line2D([0], [0], marker='o', color='w',
                   markerfacecolor='lightgrey', markeredgecolor='black',
                   markeredgewidth=0.5, markersize=10)
        ]
        if single_cluster_id is not None:
            legend_labels = [f'$Z_{{{single_cluster_id + 1}}}$'] + ['other or no cluster']
        else:
            legend_labels = [f'$Z_{{{i + 1}}}$' for i in range(n_clusters)] + ['no cluster']
        add_cluster_legend(legend_handles, legend_labels, config, ax)

    # Get cluster labels
    cluster_labels = [list(compress(objects.indices, c)) for c in in_cluster]

    return cluster_labels, cluster_colors


def render_idw_map(
    results: Results,
    objects: Objects,
    locations_map_crs: NDArray[float],
    extent: Extent,
    config: Config,
    ax: plt.Axes,
    single_cluster_id: int | None = None,

) -> tuple[list[list[int]], list[str]]:
    """Render IDW interpolation map.

    Computes an inverse distance weighted interpolation of cluster colors
    over a grid, producing a smooth color field showing cluster influence
    across the map area.

    Args:
        results: MCMC results containing cluster samples.
        objects: Objects container with site indices.
        locations_map_crs: Site locations in map CRS, shape (n_sites, 2).
        extent: Spatial extent of the map.
        config: Combined plot and style configuration.
        ax: Matplotlib axis to draw on.
        single_cluster_id: ID of a single cluster. If provided, plot a single cluster instead of all clusters. Defaults to None.

    Returns:
        Tuple of (cluster_labels, cluster_colors).
    """

    experiment = config.experiment.plots.map
    graphics = config.style.map.graphics
    legend = config.style.map.legend

    # Transparent base map for IDW — polygons drawn on top later
    bbox = box(
        minx=extent.x_min, miny=extent.y_min,
        maxx=extent.x_max, maxy=extent.y_max,
    )
    extent_file = add_basemap_polygon(config, bbox, ax)
    merged_polygon = unary_union(extent_file['geometry'])
    n_clusters = results.n_clusters

    # Get per-point frequencies and colors
    cluster_colors = get_cluster_colors(
        n_clusters=n_clusters,
        custom_colors=config.style.global_.cluster_colors or None,
    )
    if single_cluster_id is not None:
        clusters = results.clusters[single_cluster_id:single_cluster_id + 1]
        cluster_colors = cluster_colors[single_cluster_id:single_cluster_id + 1]
    else:
        clusters = results.clusters

    in_cluster = get_dominant_cluster(clusters, config)
    in_any_cluster = np.any(in_cluster, axis=0)

    # Use the dominant cluster or if below threshold use white
    dominant_color =  np.array(cluster_colors)[np.argmax(in_cluster, axis=0)]
    dominant_color = np.where(in_any_cluster, dominant_color, "white")

    # Build point GeoDataFrame with RGB channels
    rgb = np.array([
        [int(v * 255) for v in colors.to_rgb(str(c))]
        for c in dominant_color
    ])

    red, green, blue = rgb[:, 0], rgb[:, 1], rgb[:, 2]

    df = pd.DataFrame({
        'x': locations_map_crs[:, 0],
        'y': locations_map_crs[:, 1],
        'red': red,
        'green': green,
        'blue': blue,
    })

    point_geo = gpd.GeoDataFrame(
        df, geometry=[Point(x, y) for x, y in zip(df.x, df.y)]
    )

    # Compute IDW grid
    idw_grid = compute_idw_grid(
        extent_polygon=merged_polygon,
        point_rgb=point_geo,
        delta= experiment.idw.resolution,
        power=experiment.idw.power,
        background_weight=experiment.idw.background_weight,
    )

    style_axes(extent, ax)
    visualise_basemap(extent, config, ax)
    idw_grid.plot(ax=ax, color=idw_grid.idw_hex)

    # Scale point size by posterior frequency if requested
    if graphics.clusters.size == "frequency":
        point_size = graphics.clusters.max_size
    else:
        point_size = graphics.clusters.size

    # Plot points
    point_geo.plot(ax=ax, color=dominant_color,
                   markersize = point_size,
                   edgecolor='black')

    # Legend
    if legend.clusters.add:
        legend_handles = [
                             Line2D([0], [0], marker='s', color='w',
                                    markerfacecolor=col, markeredgecolor='black',
                                    markeredgewidth=0.5, markersize=10)
                             for col in cluster_colors
                         ] + [
                             Line2D([0], [0], marker='s', color='w',
                                    markerfacecolor='white', markeredgecolor='black',
                                    markeredgewidth=0.5, markersize=10)
                         ]
        if single_cluster_id is not None:
            legend_labels = [f'$Z_{{{single_cluster_id + 1}}}$'] + ['other or no cluster']
        else:
            legend_labels = [f'$Z_{{{i + 1}}}$' for i in range(n_clusters)] + ['no cluster']
        add_cluster_legend(legend_handles, legend_labels, config, ax)

    # Cluster labels
    cluster_labels = [list(compress(objects.indices, c)) for c in in_cluster]

    return cluster_labels, cluster_colors


def plot_map(
    results: Results,
    data: Data,
    config: Config,
    model: str | None = None,
    map_type: Literal['pie', 'line', 'idw'] = 'line',
    single_cluster_id: None | int = None
) -> None:
    """Plot the posterior map.

    Dispatches to pie, line or idw map based on config type setting.

    Args:
        results: MCMC results containing cluster samples.
        data: Objects, features and confounders for the experiment.
        config: Combined plot and style configuration.
        model: sBayes model name, e.g., K1 (optional).
        map_type: Type of map to create, either 'pie', 'line' or 'idw'.
        single_cluster_id: ID of a single cluster. If provided, plot a single cluster instead of all clusters. Defaults to None.
    """
    objects, features, confounders = data
    experiment = config.experiment
    style = config.style.map
    global_ = config.style.global_

    # Close any open figures
    plt.close('all')

    fig, ax = plt.subplots(
        figsize=(style.output.width, style.output.height),
        constrained_layout=True,
    )

    # Reproject locations
    locations_map_crs = reproject_locations(
        objects.locations,
        data_proj=experiment.data.projection,
        map_proj=style.geo.resolve_projection(experiment.data.projection),
    )
    # Compute extent
    extent = compute_extent(locations_map_crs, pad = 0.1)

    # Initialise the map with site scatter
    ax.scatter(
        *locations_map_crs.T,
        s=style.graphics.objects.size,
        color=style.graphics.objects.color,
        linewidth=0,
    )
    ax.set_facecolor(style.graphics.basemap.background)

    style_axes(extent, ax)

    # Render map type
    if map_type == "pie":
        visualise_basemap(extent, config, ax)
        cluster_labels, cluster_colors = render_pie_map(
            results, objects, locations_map_crs, config, ax, single_cluster_id
        )

    elif map_type == "line":
        visualise_basemap(extent, config, ax)
        cluster_labels, cluster_colors = render_line_map(
            results, objects, locations_map_crs, config, ax, single_cluster_id
        )

    elif map_type == "idw":
        cluster_labels, cluster_colors = render_idw_map(
            results, objects, locations_map_crs, extent, config, ax, single_cluster_id
        )
    else:
        raise ValueError(f"Unknown map type: {map_type}")

    # Add language labels
    if experiment.plots.map.labels in ('all', 'in_cluster'):
        add_labels(
            locations_map_crs, cluster_labels, cluster_colors,
            extent, config, ax,
        )

    # Add confounder shapes
    confounder_name = experiment.plots.map.plot_confounder

    if confounder_name and confounder_name in confounders and experiment.plots.map.type != "idw":
        confounder = confounders[confounder_name]
        add_confounder_shapes(
            confounder_name, confounder.group_assignment, confounder.group_names,
            locations_map_crs, config, ax,
        )

    # Add lines legend
    add_lines_legend(config, ax)

    # Add overview map
    add_overview_map(locations_map_crs, extent, config, ax)

    # Add index table
    if style.legend.index_table.add and style.graphics.objects.label:
        add_index_table(objects, cluster_labels, cluster_colors,
                        config, ax)

    if single_cluster_id is not None:
        map_name = f'{map_type}_map_Z{single_cluster_id+1}'
    else:
        map_name = f'{map_type}_map'

    # Save
    if model is not None:
        path_out = config.experiment.results.path_out / to_folder_name(model) / 'map'
    else:
        path_out = config.experiment.results.path_out / 'map'

    path_out.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path_out / f'{map_name}.{global_.format}',
        bbox_inches='tight',
        dpi=global_.resolution,
        format=global_.format,
    )

    plt.close(fig)


def plot_maps(
    results: Results,
    data: Data,
    config: Config,
    model: str | None = None
):
    """Wrapper function for plot_map. Iterates over map types and optionally over clusters.

    Args:
        results: MCMC results containing cluster samples.
        data: Objects, features and confounders for the experiment.
        config: Combined plot and style configuration.
        model: sBayes model name, e.g., K1 (optional).
    """
    map_config = config.experiment.plots.map
    map_types = map_config.type if isinstance(map_config.type, list) else [map_config.type]

    for map_type in map_types:
        if map_config.per_cluster:
            for cluster_idx in range(results.n_clusters):
                plot_map(results, data, config, model, map_type, cluster_idx)
        else:
            plot_map(results, data, config, model, map_type)