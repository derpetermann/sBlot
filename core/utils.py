import colorsys
import geopandas as gpd
import math
import numpy as np

from dataclasses import dataclass
from matplotlib import colors
from numpy.typing import NDArray
from pathlib import Path

from scipy.spatial import Delaunay, cKDTree
from scipy.sparse import csr_matrix
from shapely import polygonize, unary_union
from shapely.geometry import Polygon, LineString, box
from shapely.prepared import prep


@dataclass
class Extent:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def to_bbox(self) -> Polygon:
        return box(minx=self.x_min, miny=self.y_min,
                   maxx=self.x_max, maxy=self.y_max)


def compute_extent(locations: NDArray[float], pad: float = 0.05) -> Extent:
    """Computes the spatial extent from locations with optional padding.

    Args:
        locations: Array of shape (n_sites, 2) with x, y coordinates.
        pad: Fractional padding to add around the extent.
    Returns:
        Extent with x_min, x_max, y_min, y_max.
    """
    x_min, x_max = padded_range(locations[:, 0], pad=pad)
    y_min, y_max = padded_range(locations[:, 1], pad=pad)
    return Extent(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)


def padded_range(x: NDArray[float], pad: float = 0.05) -> tuple[float, float]:
    """Computes the minimum and maximum of an array with padding relative to
    the total range: lower - pad*(max-min), upper + pad*(max-min).

    Args:
        x: 1D array of numeric values.
        pad: Fractional padding relative to the range.
    Returns:
        Range. Tuple of (padded_min, padded_max).
    """
    lower = np.min(x)
    upper = np.max(x)
    diff = upper - lower
    return lower - pad * diff, upper + pad * diff


def get_corner_points(n: int, offset: float = 0.5 * np.pi) -> NDArray[float]:
    """Generates corner points of a regular n-gon on the unit circle.
    Used to project probability simplex samples into 2D for plotting.

    Args:
        n: Number of corners.
        offset: Angular offset in radians (default places first corner at top).
    Returns:
        Array of shape (n, 2) with (x, y) coordinates of the corners.
    """
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False) + offset
    return np.array([np.cos(angles), np.sin(angles)]).T


def clip_grid_to_polygon(geom: Polygon, delta: float) -> list[Polygon]:
    """Partition a polygon into a regular grid of cells.

    Generates a regular grid over the bounding box of `geom` and retains
    only cells whose centroid falls inside the polygon. The function uses a prepared
    geometry for efficient repeated containment checks.

    Args:
        geom: Polygon defining the spatial extent of the clip.
        delta: Grid cell size in the same units as the polygon CRS.
    Returns:
        List of Polygons representing the grid cells inside `geom`.
    """
    prepared_geom = prep(geom)
    return [cell for cell in build_grid(geom, delta)
            if prepared_geom.contains(cell.centroid)]


def build_grid(geom: Polygon, delta: float) -> list[Polygon]:
    """Generate a regular grid of rectangular cells over a polygon's bounding box.

    Args:
        geom: Polygon whose bounding box defines the grid extent.
        delta: Grid cell size in the same units as the polygon CRS.
    Returns:
        List of rectangular Polygons covering the bounding box of `geom`.
        Use `clip_grid_to_polygon()` to restrict to the polygon interior.
    """
    minx, miny, maxx, maxy = geom.bounds
    nx = int((maxx - minx) / delta)
    ny = int((maxy - miny) / delta)
    gx = np.linspace(minx, maxx, nx)
    gy = np.linspace(miny, maxy, ny)

    return [
        Polygon([[gx[i], gy[j]], [gx[i], gy[j+1]],
                 [gx[i+1], gy[j+1]], [gx[i+1], gy[j]]])
        for i in range(len(gx) - 1)
        for j in range(len(gy) - 1)
    ]


def compute_idw_grid(
    extent_polygon: Polygon,
    point_rgb: gpd.GeoDataFrame,
    delta: float,
    idw_power: int = 2,
    background_weight: float = 1.0,
    background_color: tuple[int, int, int] = (255, 255, 255),
) -> gpd.GeoDataFrame:
    """Interpolate RGB colors over a polygon grid using Inverse Distance Weighting.

    Generates a regular grid over `extentpoly`, then interpolates the RGB color
    values from `point_rgb` onto each grid cell using IDW. The background color
    is weighted relative to the diagonal of the extent polygon, so that the
    interpolation decays gracefully in areas far from any input point.

    The background weight is scaled by the IDW weight of a hypothetical point
    at 1/8 of the diagonal distance — a heuristic that gives visually pleasing
    results for typical map extents.

    Args:
        extent_polygon: Polygon defining the spatial extent of the grid.
        point_rgb: GeoDataFrame with columns 'x', 'y', 'red', 'green', 'blue'
                   containing the input point locations and RGB color values.
        delta: Grid cell size in the same units as the polygon CRS.
        idw_power: Power parameter controlling distance decay.
        background_weight: Relative weight of the background color. Higher
                           values pull interpolation toward the background
                           color in areas far from input points.
        background_color: RGB tuple for the background color. Defaults to
                          white (255, 255, 255).
    Returns:
        GeoDataFrame with the grid cells and columns 'red', 'green', 'blue',
        and 'idw_hex' containing the interpolated colors.
    """
    # Build a regular grid clipped to the extent polygon
    grid = gpd.GeoDataFrame(geometry=gpd.GeoSeries(clip_grid_to_polygon(extent_polygon, delta)))

    # Scale background weight relative to the map diagonal.
    # A background point at 1/8 of the diagonal gives visually pleasing
    # decay at the edges — tuned empirically on the Balkans dataset.
    minx, miny, maxx, maxy = extent_polygon.bounds
    dist_diag = math.sqrt((maxx - minx) ** 2 + (maxy - miny) ** 2)
    scaled_background_weight = background_weight / ((dist_diag / 8) ** idw_power)

    # Grid cell centroids as coordinate arrays
    grid_centroids = grid.geometry.centroid
    grid_x = grid_centroids.x.to_numpy()
    grid_y = grid_centroids.y.to_numpy()
    point_x = point_rgb.x.to_numpy()
    point_y = point_rgb.y.to_numpy()

    # Interpolate each RGB channel independently
    for channel, bg_value in zip(['red', 'green', 'blue'], background_color):
        grid[channel] = standard_idw(
            grid_lon=grid_x,
            grid_lat=grid_y,
            longs=point_x,
            lats=point_y,
            point_values=point_rgb[channel].to_numpy(),
            id_power=idw_power,
            background_weight=scaled_background_weight,
            background_value=bg_value,
        ).astype(int)

    grid['idw_hex'] = [colors.to_hex((r / 255, g / 255, b / 255))
                       for r, g, b in zip(grid.red, grid.green, grid.blue)]

    return grid

def standard_idw(
    grid_lon: NDArray[float],
    grid_lat: NDArray[float],
    longs: NDArray[float],
    lats: NDArray[float],
    point_values: NDArray[float],
    id_power: int = 2,
    background_weight: float = 0.0,
    background_value: float = 0.0,
) -> NDArray[float]:
    """Interpolate values at grid points using Inverse Distance Weighting (IDW).

    Each grid point receives a weighted average of the input values, where the
    weight of each input point decreases with distance raised to `id_power`.
    A constant background value can be added to control behaviour in areas
    far from any input point.

    Args:
        grid_lon: Longitudes of grid points, shape (ny, nx) or (n,).
        grid_lat: Latitudes of grid points, shape (ny, nx) or (n,).
        longs: Longitudes of input points, shape (m,).
        lats: Latitudes of input points, shape (m,).
        point_values: Values at input points, shape (m,).
        id_power: Power parameter controlling distance decay. Higher values
                  give more influence to nearby points.
        background_weight: Weight of the background value, which should already be
                           scaled relative to the spatial extent by the caller.
        background_value: Value the interpolation decays to in areas far from
                          any input point.
    Returns:
        Interpolated values at grid points, same shape as grid_lon.
    """
    # Remember the original grid shape so we can restore it after flattening
    grid_shape = grid_lon.shape
    grid_lon = grid_lon.flatten()
    grid_lat = grid_lat.flatten()

    # Euclidean distance from each grid point to each input point
    # Shape: (n_grid_points, n_input_points)
    dists = np.sqrt((longs[np.newaxis, :] - grid_lon[:, np.newaxis]) ** 2 +
                    (lats[np.newaxis, :] - grid_lat[:, np.newaxis]) ** 2)

    # IDW weights: w = 1 / (id^power)
    with np.errstate(divide='ignore', invalid='ignore'):
        weights = np.where(dists == 0, np.inf, 1 / dists ** id_power)

    # Weighted average of input values with optional background term
    sum_weighted_values = (background_value * background_weight +
                           np.sum(point_values[None, :] * weights, axis=1))
    sum_weights = background_weight + np.sum(weights, axis=1)

    return (sum_weighted_values / sum_weights).reshape(grid_shape)


def compute_alpha_shape(points: NDArray[float], alpha: float) -> Polygon:
    """Compute the alpha shape (concave hull) of a set of points.

    The alpha shape is a generalisation of the convex hull — smaller alpha
    values produce a tighter, more concave shape. If alpha is too large,
    the shape may become empty or disconnected.

    Args:
        points: Array of shape (n_points, 2) with x, y coordinates.
        alpha: Controls concavity. Larger values produce a tighter shape;
               too large and interior points may be lost.
    Returns:
        Shapely Polygon representing the alpha shape. May be empty if
        alpha is too large for the point configuration.
    """

    def add_edge(i: int, j: int) -> None:
        if (i, j) not in edges and (j, i) not in edges:
            edges.add((i, j))
            edge_nodes.append(points[[i, j]])

    tri = Delaunay(points, qhull_options="QJ Pp")

    edges = set()
    edge_nodes = []

    for ia, ib, ic in tri.simplices:
        pa, pb, pc = points[ia], points[ib], points[ic]

        # Side lengths
        a = math.sqrt((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2)
        b = math.sqrt((pb[0] - pc[0]) ** 2 + (pb[1] - pc[1]) ** 2)
        c = math.sqrt((pc[0] - pa[0]) ** 2 + (pc[1] - pa[1]) ** 2)

        # Circumradius via Heron's formula
        s = (a + b + c) / 2.0
        area = math.sqrt(s * (s - a) * (s - b) * (s - c))
        circum_r = a * b * c / (4.0 * area)

        # Keep triangle if circumradius is within the alpha threshold
        if circum_r < 1.0 / alpha:
            add_edge(ia, ib)
            add_edge(ib, ic)
            add_edge(ic, ia)

    lines = [LineString(edge) for edge in edge_nodes]
    triangles = list(polygonize(lines))
    return unary_union(triangles)


def lighten_color(color: tuple[float, float, float], amount: float = 0.2) -> tuple[float, float, float]:
    """Lighten an RGB color by blending it toward white.

    Args:
        color: RGB tuple with values in [0, 1].
        amount: Blending factor toward white. 0.0 returns the original
                color, 1.0 returns white.
    Returns:
        Lightened RGB tuple with values in [0, 1].
    """
    h, l, s = colorsys.rgb_to_hls(*color)
    return colorsys.hls_to_rgb(h, 1 - amount * (1 - l), s)


def parse_cluster_columns(clusters_encoded: str) -> NDArray[float]:
    """Parse a tab-separated string of cluster assignments into a numeric array.

    Each tab-separated token represents one cluster, encoded as a
    whitespace-separated sequence of values indicating cluster membership
    for each object. Values can be binary (0/1) for hard assignment or
    float in [0, 1] for soft (probabilistic) assignment.

    Args:
        clusters_encoded: Tab-separated string of cluster encodings, one per
                          cluster. Example: '0 1 1 0\\t1 0 0 1'
    Returns:
        Float array of shape (n_clusters, n_objects) with values in [0, 1].
    Raises:
        ValueError: If the input string is empty.
    """
    if not clusters_encoded.strip():
        raise ValueError("Cannot parse empty cluster string.")
    return np.array([c.split() for c in clusters_encoded.split('\t')], dtype=float)


def format_cluster_columns(clusters: NDArray[bool | float]) -> str:
    """Format an array of cluster assignments as a tab-separated string.

    Inverse of `parse_cluster_columns`. Each cluster is encoded as a
    space-separated sequence of values, with clusters separated by tabs.

    Args:
        clusters: Boolean or float array of shape (n_clusters, n_objects)
                  with cluster membership values in [0, 1].
    Returns:
        Tab-separated string of encoded cluster assignments.
    """
    return '\t'.join(encode_cluster(cluster) for cluster in clusters)


def encode_cluster(cluster: NDArray[bool | float]) -> str:
    """Format a cluster's assignments as an encoded string.

    For boolean (hard) assignments, encodes as a compact bit-string with no
    separator e.g. '0110'. For probabilistic assignments, encodes as a
    space-separated string e.g. '0.8 0.1 0.9 0.2' to allow unambiguous
    parsing.

    Args:
        cluster: Boolean or float array of shape (n_objects, ) with cluster
                 membership values.
    Returns:
        Encoded string of cluster assignments.
    """
    if cluster.dtype == bool:
        # Compact bit-string for hard assignments — backward compatible
        return ''.join(cluster.astype(int).astype(str))
    # Space-separated for float assignments — required for unambiguous parsing
    return ' '.join(f'{v:.6f}' for v in cluster)


def write_clusters(filename: str | Path, cluster_samples: NDArray[bool | float]) -> None:
    """Write cluster assignments to a text file.

    Inverse of `load_clusters`. Each line represents one MCMC sample,
    formatted as tab-separated cluster encodings.

    Args:
        filename: Path to the output file.
        cluster_samples: Array of shape (n_samples, n_clusters, n_objects)
                         with binary or float cluster assignments.
    """
    with open(filename, 'w') as clusters_file:
        clusters_file.writelines(
            format_cluster_columns(sample) + "\n" for sample in cluster_samples
        )


def cluster_agreement(
    a1: NDArray[float],
    a2: NDArray[float],
) -> NDArray[float]:
    """Compute pairwise agreement between two sets of cluster assignments.

    Computes the dot product between mean cluster assignments from two runs,
    producing a matrix where entry (i, j) reflects how much cluster i in run 1
    agrees with cluster j in run 2. Used to find the optimal cluster label
    permutation across runs.

    Args:
        a1: Mean cluster assignments from run 1, shape (n_clusters, n_objects).
        a2: Mean cluster assignments from run 2, shape (n_clusters, n_objects).
    Returns:
        Agreement matrix of shape (n_clusters, n_clusters).
    """
    return np.matmul(a1, a2.T)


def get_cluster_colors(n_clusters: int, custom_colors: list[str] | None = None) -> list[str]:
    """Generate a list of visually distinct colors for cluster visualization.

    Colors are generated in HSV space with alternating saturation and value
    to maximise visual distinction between adjacent clusters. If custom colors
    are provided, they are used first and default colors fill the remainder.

    Args:
        n_clusters: Total number of colors needed.
        custom_colors: Optional list of hex color strings to use first.
                       Must have fewer entries than `n_clusters`.
    Returns:
        List of hex color strings of length `n_clusters`.
    """
    if custom_colors is None:
        custom_colors = []
        for i, h in enumerate(np.linspace(0, 1, n_clusters, endpoint=False)):
            # Alternate saturation and value to distinguish adjacent colors
            b = i % 2
            s = 0.6 + 0.4 * (1 - b)
            v = 0.5 + 0.3 * b
            custom_colors.append(colors.to_hex(colorsys.hsv_to_rgb(h, s, v)))
        return custom_colors
    else:
        n_additional = n_clusters - len(custom_colors)
        additional = get_cluster_colors(n_additional)
        return list(custom_colors) + additional


def compute_delaunay(locations: NDArray[float]) -> csr_matrix:
    """Compute the Delaunay triangulation of a set of 2D point locations.

    Returns a sparse adjacency matrix where entry (i, j) is 1 if sites i
    and j are connected in the Delaunay triangulation. For fewer than 4
    points, returns a fully connected graph since scipy's Delaunay
    triangulation requires at least 4 points.

    Args:
        locations: Array of shape (n_sites, 2) with x, y coordinates
                   in a metric CRS.
    Returns:
        Sparse adjacency matrix of shape (n_sites, n_sites) representing
        the Delaunay triangulation.
    """
    n = len(locations)

    # scipy's Delaunay requires at least 4 points — fall back to fully connected graph
    if n < 4:
        return csr_matrix(1 - np.eye(n, dtype=int))

    delaunay = Delaunay(locations, qhull_options="QJ Pp")
    indptr, indices = delaunay.vertex_neighbor_vertices
    data = np.ones_like(indices)

    return csr_matrix((data, indices, indptr), shape=(n, n))


def gabriel_graph_from_delaunay(
    delaunay: csr_matrix,
    locations: NDArray[float],
) -> NDArray[int]:
    """Compute the Gabriel graph from a Delaunay triangulation.

    The Gabriel graph is a subgraph of the Delaunay triangulation where an
    edge (i, j) is retained only if no other point lies within the circle
    whose diameter is the edge. This produces a sparser, more locally
    meaningful graph than the full Delaunay triangulation.

    Args:
        delaunay: Sparse adjacency matrix of the Delaunay triangulation,
                  shape (n_sites, n_sites), as returned by `compute_delaunay`.
        locations: Array of shape (n_sites, 2) with x, y coordinates
                   in a metric CRS.
    Returns:
        Integer array of shape (n_gabriel_edges, 2) with indices of
        connected site pairs in the Gabriel graph.
    """
    # Extract unique edges from upper triangle of adjacency matrix
    adjacency = delaunay.toarray() > 0
    i1, i2 = np.where(np.triu(adjacency, k=1))
    delaunay_connections = np.column_stack([i1, i2])
    delaunay_locations = locations[delaunay_connections]

    # Midpoint and radius of the diameter circle on each Delaunay edge
    m = (delaunay_locations[:, 0, :] + delaunay_locations[:, 1, :]) / 2
    r = np.sqrt(np.sum((delaunay_locations[:, 0, :] -
                        delaunay_locations[:, 1, :]) ** 2, axis=1)) / 2

    # Retain edge (i, j) if no point lies strictly inside its diameter circle.
    # Use isclose for the boundary case to handle floating point precision errors.
    tree = cKDTree(locations)
    nearest_dist = tree.query(x=m, k=1)[0]
    is_gabriel_edge = (nearest_dist >= r) | np.isclose(nearest_dist, r)

    return delaunay_connections[is_gabriel_edge]


def fix_relative_path(path: str | Path, base_directory: str | Path) -> Path:
    """Resolve a path relative to a base directory if not already absolute.

    Args:
        path: The original path, either absolute or relative.
        base_directory: The directory to resolve relative paths against,
                        typically the config file's parent directory.
    Returns:
        Absolute Path object.
    """
    path = Path(path)
    return path if path.is_absolute() else base_directory / path


def decompose_config_path(config_path: Path | str) -> (Path, Path):
    """Extract the base directory of `config_path` and return the path itself as an
    absolute path."""
    abs_config_path = Path(config_path).absolute()
    base_directory = abs_config_path.parent
    return base_directory, abs_config_path



