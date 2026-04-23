from __future__ import annotations

# todo: remove after installation
# from here
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, '/home/peter/Desktop/sBayes/sBayes')
# until here

import base64
import numpy as np
import os;os.environ['USE_PYGEOS'] = '0'  # Fix for Pandas deprecation warning
import pandas as pd

from dash import dcc, no_update, html
from dash_extensions.enrich import (Output, DashProxy, Input,
                                    MultiplexerTransform, State)
from io import StringIO
from pathlib import Path
from plotly import graph_objects as go
from sbayes.load_data import Confounder, Objects, read_data_csv
from sbayes.results import Results
from sblot.core.utils import (activate_verbose_warnings, find_biggest_angle_gap,
                              get_cluster_colors, reproject_locations)
from sblot.core.render import COLOR_HIGHLIGHT, COLOR_NEUTRAL
from sblot.interactive import components
from sblot.interactive.app_state import AppState
from sblot.interactive.plotting import plot_summary_map, plot_sample_map, initialize_data_map


def parse_content(content: str | bytes) -> str:
    """Decode base64-encoded file content uploaded via a Dash dcc.Upload component.

    Dash encodes uploaded files as base64 strings prefixed with a data URL
    header (e.g. 'data:text/csv;base64,...'). This function strips the header,
    decodes the base64 content and restores tab and newline characters.

    Args:
        content: Base64-encoded file content, either as a data URL string
                 or raw base64 bytes.
    Returns:
        Decoded file content as a plain string.
    """
    if isinstance(content, str):
        _, content = content.split(',')
    content = str(base64.b64decode(content))[2:-1]
    return content.replace(r"\t", "\t").replace(r"\n", "\n")


def encode_content(content: bytes) -> bytes:
    """Encode file content as base64 for use with a Dash dcc.Upload component.

    Inverse of parse_content — encodes raw file bytes into base64 for
    programmatic upload of files to the Dash app without user interaction.

    Args:
        content: Raw file content as bytes.
    Returns:
        Base64-encoded file content as bytes.
    """
    return base64.b64encode(content)


# Initialized app
app = DashProxy(
    prevent_initial_callbacks='initial_duplicate',  # type: ignore[arg-type]
    transforms=[MultiplexerTransform()],
    suppress_callback_exceptions=True,
)
server = app.server
state = AppState()



@app.callback(
    Output('dashboard', 'children'),
    Output('upload-clusters', 'disabled'),
    Output('upload-data', 'children'),
    Input('upload-data', 'contents'),
    Input('upload-data', 'filename'),
    prevent_initial_call=True
)
def update_data(
    content: str | None,
    filename: str | None,
) -> tuple[dcc.Tabs, bool, html.Div] | None:
    """Load and process a data CSV file uploaded by the user.

    Parses the uploaded file, builds object and confounder data structures,
    reprojects locations and initialises the data map figure. Updates the
    application state and rebuilds the dashboard layout.

    If content is None and data is already loaded, return the existing
    dashboard. If content is None and no data is loaded, return None to
    leave the layout unchanged.

    Args:
        content: Base64-encoded file content from the dcc.Upload component,
                 or None if no file was uploaded.
        filename: Name of the uploaded file, or None.
    Returns:
        Tuple of (dashboard layout, clusters upload enabled, upload label)
        or None if no content and no data is loaded.
    """
    if content is None:
        if state.data is None:
            return None
        else:
            return components.build_tabs(state), False, html.Div([state.data_filename])

    # Parse and load data
    data_str = parse_content(content)
    data_file = StringIO(data_str)
    state.data_filename = filename
    state.data = data = read_data_csv(data_file)  # type: ignore[arg-type]
    state.objects = objects = Objects.from_dataframe(data)
    state.groups = groups = Confounder.from_dataframe(data, confounder_name=state.confounder)

    # Reproject locations and adjust longitude cut to minimise map distortion
    state.locations = locations = reproject_locations(
        objects.locations, state.data_crs, "epsg:4326"
    )
    cut_longitude = find_biggest_angle_gap(locations[:, 0])
    locations[:, 0] = (locations[:, 0] - cut_longitude) % 360 + cut_longitude
    n_objects = len(locations)

    # Build per-object group assignment
    group_names = np.array(groups.group_names + [""])
    group_ids = []
    for i, obj in enumerate(objects.names):
        i_g = np.flatnonzero(groups.group_assignment[:, i])
        i_g = i_g[0] if len(i_g) > 0 else groups.n_groups
        group_ids.append(i_g)
    group_ids = np.array(group_ids)

    # Build object data DataFrame
    state.object_data = pd.DataFrame({
        "x": locations[:, 0],
        "y": locations[:, 1],
        "name": objects.names,
        state.confounder: group_names[group_ids],
        "cluster": np.zeros(n_objects, dtype=int),
        "posterior_support": np.zeros(n_objects),
    })

    # Initialise data map figure
    state.data_fig = initialize_data_map(state)

    return components.build_tabs(state), False, html.Div([filename])


@app.callback(
    Output('results-tab', 'children'),
    Output('results-tab', 'disabled'),
    Output('tabs', 'value'),
    Output('upload-clusters', 'children'),
    Input('upload-clusters', 'contents'),
    Input('upload-clusters', 'filename'),
    prevent_initial_call=True
)
def update_clusters(
    content: str | None,
    filename: str | None,
) -> tuple[html.Div, bool, str, html.Div] | None:
    """Load and process a cluster file uploaded by the user.

    Parses the uploaded clusters file, stores the cluster samples in the
    application state and rebuilds the Results tab layout. Enables the
    Results tab and switches to it automatically.

    Args:
        content: Base64-encoded file content from the dcc.Upload component,
                 or None if no file was uploaded.
        filename: Name of the uploaded file, or None.
    Returns:
        Tuple of (Results layout, results tab enabled, active tab, upload label)
        or None if no content was uploaded.
    """
    if content is None:
        return None

    # Parse and store cluster samples
    state.clusters_path = Path(filename)
    clusters_str = parse_content(content)
    state.clusters = Results.read_clusters_from_str(clusters_str)

    # Build Results layout and switch to Results tab
    results_components = components.build_results_components(state)
    return results_components, False, "results-tab", html.Div([filename])


@app.callback(
    Output("data_map", "figure"),
    Input("group-sizes", "hoverData"),
    prevent_initial_call=True
)

def hover_group(hover_data: dict) -> go.Figure:
    """Highlight objects belonging to the hovered group of a confounder on the data map.

    When the user hovers over a bar in the group sizes chart, colors all
    objects in that group with the highlight color and all other objects
    with the neutral color.

    Args:
        hover_data: Plotly hover event data containing the hovered group
                    name in hover_data["points"][0]["x"].
    Returns:
        The updated data map figure.
    """
    group = hover_data["points"][0]["x"]
    in_group = state.object_data[state.confounder] == group
    state.data_fig.update_traces(marker={
        "color": np.where(in_group, COLOR_HIGHLIGHT, COLOR_NEUTRAL)
    })
    return state.data_fig


@app.callback(
    Output('data_map', 'figure'),
    Input('feature-selector', 'value'),
    prevent_initial_call=True
)
def select_feature(feature: str) -> go.Figure:
    """Color the data map by the selected feature value.

    When the user selects a feature from the radio items in the Features
    subtab, colors each object on the data map according to its value for
    that feature. Objects with missing values are colored with the neutral
    color.

    Args:
        feature: Name of the selected feature column in the data DataFrame.
    Returns:
        The updated data map figure.
    """
    # Get unique non-null states for this feature
    feature_states = state.data[feature].unique()
    feature_states = feature_states[~pd.isna(feature_states)]

    # Create color palette — one color per state plus neutral for missing values
    color_seq = get_cluster_colors(len(feature_states))
    color_map = {s: color_seq[i] for i, s in enumerate(feature_states)}
    color_map[np.nan] = COLOR_NEUTRAL

    # Color the map by feature value
    colors = [color_map[x] for x in state.data[feature]]
    state.data_fig.update_traces(marker={"color": colors})
    return state.data_fig


@app.callback(
    Output("map", "figure"),
    Input("i_sample", "value"),
    prevent_initial_call=True
)
def update_sample_map(i_sample: int) -> go.Figure | None:
    """Update the Results map to show a single posterior sample.

    Triggered when the user moves the sample slider. Updates the map to
    show cluster assignments for the selected posterior sample.

    Args:
        i_sample: Index of the posterior sample to display.
    Returns:
        The updated results map figure, or None if no clusters are loaded.
    """
    if state.clusters is None:
        return None

    state.i_sample = i_sample
    return plot_sample_map(state, i_sample)


@app.callback(
    Output("map", "figure"),
    Output("i_sample", "value"),
    Input("trace", "hoverData"),
    State("summarize_switch", "on"),
    prevent_initial_call=True
)
def hover_tracer(
    hover_data: dict,
    summarize: bool,
) -> tuple[go.Figure, int | type(no_update)]:
    """Highlight a cluster when the user hovers over the trace plot.

    In summary mode, enlarges markers for objects in the hovered cluster
    without changing the sample slider. In sample mode, jumps to the
    hovered sample index and updates the sample slider accordingly.

    Args:
        hover_data: Plotly hover event data containing the hovered cluster
                    index in hover_data["points"][0]["curveNumber"] and the
                    sample index in hover_data["points"][0]["x"].
        summarize: Whether the app is currently in summary mode.
    Returns:
        Tuple of (updated figure, new sample slider value or no_update).
    """
    cluster = hover_data["points"][0]["curveNumber"]
    state.highlighted_cluster = cluster

    if summarize:
        # Enlarge markers for objects in the hovered cluster
        in_cluster = state.object_data.cluster == cluster
        state.fig.update_traces(marker={"size": np.where(in_cluster, 10, 5)})
        return state.fig, no_update
    else:
        # Jump to the hovered sample
        sample = hover_data["points"][0]["x"]
        return state.fig, sample


@app.callback(
    Output("map", "figure"),
    Input("sample_range", "value"),
    prevent_initial_call=True
)
def update_summary_map(sample_range: list[int]) -> go.Figure | None:
    """Update the Results map to show a summary over a range of posterior samples.

    Triggered when the user moves the range slider. Computes mean cluster
    assignments over the selected sample range and updates the map accordingly.

    Args:
        sample_range: [i_start, i_end] indices defining the range of posterior
                      samples to summarise.
    Returns:
        The updated results map figure, or None if no clusters are loaded.
    """
    if state.clusters is None:
        return None

    state.i_start, state.i_end = sample_range
    return plot_summary_map(state, sample_range)


@app.callback(
    Output("map", "figure"),
    Output("slider_div", "style"),
    Output("range_slider_div", "style"),
    Input("summarize_switch", "on"),
    prevent_initial_call=True
)
def switch_summarization(
    summarize: bool,
) -> tuple[go.Figure, dict, dict]:
    """Switch between summary and single-sample display modes.

    Triggered when the user toggles the summarize switch. In summary mode
    shows the range slider and a summary map over all samples. In sample
    mode shows the sample slider and a single sample map.

    Clears the highlighted cluster when switching modes.

    Args:
        summarize: Whether to switch to summary mode (True) or single
                   sample mode (False).
    Returns:
        Tuple of (updated figure, sample slider style, range slider style).
    """
    state.highlighted_cluster = None

    sample_slider_style = {"width": "90%", "display": "none"}
    range_slider_style = {"width": "90%", "display": "none"}

    if summarize:
        map_figure = plot_summary_map(state, [0, state.n_samples])
        range_slider_style["display"] = "inline-block"
    else:
        map_figure = plot_sample_map(state, state.i_sample)
        sample_slider_style["display"] = "inline-block"

    return map_figure, sample_slider_style, range_slider_style


@app.callback(
    Output("download-map", "data"),
    Input("download-map-button", "n_clicks"),
    prevent_initial_call=True
)
def download_figure(n_clicks: int) -> dict:
    """Serialize the current results map as a downloadable HTML file.

    Triggered when the user clicks the download button. Exports the current
    results map figure as a self-contained HTML file that can be opened in
    any browser.

    Args:
        n_clicks: Number of times the download button has been clicked.
                  Not used directly but required by Dash callback signature.
    Returns:
        Dash download dict with base64-encoded HTML content.
    """
    return state.serialize_results_map(filename="sBayes_map.html")


def main(
    port: int = 8050,
    crs: str = "epsg:4326",
    data_path: Path | None = None,
    confounder: str = "family"
) -> None:
    """Start the sBlot interactive explorer app.

    Optionally, pre-loads a data file so users don't have to upload it
    manually. Set up the app layout and start the Dash development server.

    Args:
        port: Port number to serve the app on. Defaults to 8050.
        crs: Coordinate reference system of the input data as a PROJ string
             or EPSG code. Defaults to 'epsg:4326'.
        data_path: Optional path to a data CSV file to preload on startup.
                   If None, the user must upload a file through the browser.
        confounder: Name of the confounder to display. Defaults to 'family'.
    """
    state.data_crs = crs
    state.confounder = confounder

    # Preload data file if provided
    if data_path is not None:
        data_path = Path(data_path)
        with open(data_path, 'rb') as f:
            data_encoded = base64.b64encode(f.read()).decode('utf-8')
            data_url = f"data:text/csv;base64,{data_encoded}"
            update_data(data_url, data_path.name)

    app.layout = components.get_base_layout()
    app.run(debug=True, port=port)


def cli() -> None:
    """Command line entry point for the sBlot interactive explorer.

    Usage:
        sblot-interactive [-p PORT] [-c CRS] [-d DATA] [--conf CONFOUNDER]

    Examples:
        sblot-interactive
        sblot-interactive -p 8080 -d data/features.csv
        sblot-interactive -c "epsg:4326" --conf family
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive visualisation of sBayes results.",
        prog="sblot-interactive",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        nargs="?",
        default=8050,
        help="Port used to serve the application. Defaults to 8050.",
    )
    parser.add_argument(
        "-c", "--crs",
        type=str,
        nargs="?",
        default="epsg:4326",
        help="Coordinate reference system of the input data. Defaults to 'epsg:4326'.",
    )
    parser.add_argument(
        "-d", "--data",
        type=Path,
        nargs="?",
        help="Optional path to a data CSV file to pre-load on startup.",
    )
    parser.add_argument(
        "--conf",
        type=str,
        default="family",
        help="Name of the confounder column in the data CSV. Defaults to 'family'.",
    )
    cli_args = parser.parse_args()

    if __debug__:
        activate_verbose_warnings()

    main(
        port=cli_args.port,
        crs=cli_args.crs,
        data_path=cli_args.data,
        confounder=cli_args.conf,
    )


if __name__ == '__main__':
    cli()

if __name__ == '__main__':
    cli()

