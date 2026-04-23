from __future__ import annotations

import io
from base64 import b64encode
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
import pandas as pd
from plotly import graph_objects as go
from sbayes.load_data import Objects, Confounder
from sblot.core.utils import get_cluster_colors
from sblot.core.render import COLOR_NEUTRAL



@dataclass
class AppState:
    """Mutable application state shared across all Dash callbacks.

    Holds all data, figures and UI state for the sBlot explorer app.
    The cluster setter automatically recomputes cluster colors when
    new cluster data is loaded.

    Attributes:
        data_crs: Coordinate reference system of the input data.
        clusters_path: Path to the loaded clusters file.
        data: Raw features DataFrame loaded from the data CSV.
        object_data: Processed DataFrame with one row per object,
                     containing location, name, confounder and cluster columns.
        objects: Objects container with site names and locations.
        locations: Array of reprojected object locations, shape (n_objects, 2).
        confounder: Name of the confounder to show in the plot.
        groups: The Confounder object with group assignments.
        data_fig: Plotly figure for the data map tab.
        fig: Plotly figure for the Results map tab.
        lines: Tuple of line traces in the Results figure, one per cluster.
        scatter: Scatter trace in the Results figure.
        cluster_colors: Array of hex color strings, one per cluster plus one
                        for unassigned objects.
        i_sample: Index of the currently displayed posterior sample.
        highlighted_cluster: Index of the currently highlighted cluster, or
                             None if no cluster is highlighted.
    """

    # Configuration
    data_crs: str | None = None

    # Loaded data
    clusters_path: Path | None = None
    data: pd.DataFrame | None = None
    object_data: pd.DataFrame | None = None
    objects: Objects | None = None
    locations: NDArray[float] | None = None
    confounder: str | None = None
    groups: Confounder | None = None

    # Figures
    data_fig: go.Figure | None = None
    fig: go.Figure | None = None
    lines: tuple | None = None
    scatter: go.Scattergeo | None = None

    # Derived state — managed via property
    _clusters: NDArray[bool] | None = field(default=None, repr=False)
    cluster_colors: NDArray[str] | None = None

    # UI state
    i_sample: int = 0
    highlighted_cluster: int | None = None

    @property
    def clusters(self) -> NDArray[bool] | None:
        """Posterior cluster samples, shape (n_clusters, n_samples, n_objects)."""
        return self._clusters

    @clusters.setter
    def clusters(self, clusters: NDArray[bool]) -> None:
        """Set cluster samples and recompute cluster colors.

        Automatically appends COLOR_0 as the color for unassigned objects
        so that cluster_colors always has n_clusters + 1 entries.
        """
        self._clusters = clusters
        # n_clusters colors + 1 for unassigned objects
        self.cluster_colors = np.array(
            get_cluster_colors(self.n_clusters) + [COLOR_NEUTRAL]
        )

    @property
    def n_clusters(self) -> int:
        """Number of clusters in the posterior."""
        return self._clusters.shape[0]

    @property
    def n_samples(self) -> int:
        """Number of posterior samples."""
        return self._clusters.shape[1]

    @property
    def n_objects(self) -> int:
        """Number of objects in the dataset."""
        return self.objects.n_objects


    def serialize_results_map(self, filename: str) -> dict:
        """Serialize the Results map figure as a base64-encoded HTML file.

        Used by the download button callback to export the current map
        as a self-contained HTML file.

        Args:
            filename: Name of the downloaded file.
        Returns:
            Dash download dict with base64-encoded HTML content.
        """
        buffer = io.StringIO()
        self.fig.write_html(buffer)
        html_bytes = buffer.getvalue().encode()
        content = b64encode(html_bytes).decode()
        return {
            "base64": True,
            "content": content,
            "type": "text/html",
            "filename": filename,
        }