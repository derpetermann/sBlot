import dash_daq as daq
import pandas as pd
import plotly.express as px

from dash import html, dcc
from sblot.core.render import COLOR_NEUTRAL, COLOR_HIGHLIGHT
from sblot.interactive.app_state import AppState
from sblot.interactive.plotting import initialize_results_map, plot_sample_map, plot_summary_map, plot_trace
from sblot.interactive.styles import all_tab_styles, tabs_styles, upload_box_style



def get_base_layout() -> html.Div:
    """Build the base layout of the sBlot dash app.

    Creates the top-level structure with two file-upload boxes side by side
    — one for the data CSV and one for the cluster file — and an empty
    dashboard area that is populated once files are uploaded.

    The cluster upload is disabled by default and only enabled after a
    valid data file has been uploaded.

    Returns:
        A Dash html.Div containing the full base layout.
    """
    return html.Div(
        children=[
            html.Div([
                dcc.Upload(
                    id='upload-data',
                    children=html.Div([
                        'drag and drop or select the ', html.B('data file'), ' (.csv)'
                    ]),
                    style=upload_box_style,
                    disabled=False,
                    style_disabled={"opacity": 0.3},
                )
            ], style={"width": "50%", "display": "inline-block"}),
            html.Div([
                dcc.Upload(
                    id='upload-clusters',
                    children=html.Div([
                        'drag and drop or select the ', html.B('clusters file'), ' (clusters_*.txt)'
                    ]),
                    style=upload_box_style,
                    disabled=True,
                    style_disabled={"opacity": 0.3},
                )
            ], style={"width": "50%", "display": "inline-block"}),
            html.Div(id='dashboard', children=[])
        ],
        style={"font-family": "sans-serif"},
    )


def get_sample_slider(state: AppState) -> dcc.Slider:
    """Build a slider for selecting a single posterior sample to display.

    Creates a Dash slider ranging from 0 to the total number of samples
    minus one, with tick marks at approximately 10 evenly spaced positions.
    Used in the `results` tab to step through individual posterior samples.

    Args:
        state: Current application state containing the number of samples.
    Returns:
        A Dash dcc.Slider component.
    """
    return dcc.Slider(
        id="i_sample",
        value=1,
        step=1,
        min=0,
        max=state.n_samples - 1,
        marks={
            i: str(i)
            for i in range(0, state.n_samples, max(1, state.n_samples // 10))
        },
    )


def get_summary_range_slider(state: AppState) -> dcc.RangeSlider:
    """Build a range slider for selecting a range of posterior samples to summarise.

    Creates a Dash range slider ranging from 0 to the total number of samples,
    with tick marks at approximately 10 evenly spaced positions. Used in the
    `results` tab to select a subset of samples for the summary map.

    Args:
        state: Current application state containing the number of samples.
    Returns:
        A Dash dcc.RangeSlider component.
    """
    return dcc.RangeSlider(
        id="sample_range",
        value=[0, state.n_samples],
        step=1,
        min=0,
        max=state.n_samples,
        marks={
            i: str(i)
            for i in range(0, state.n_samples, max(1, state.n_samples // 10))
        },
    )


def build_tabs(state: AppState) -> dcc.Tabs:
    """Build the main tab container with Data and Results tabs.

    Creates two tabs — Data and Results. The Data tab is immediately
    populated with the data component. The Results tab is empty and
    disabled until a cluster file has been uploaded.

    Args:
        state: Current application state containing loaded data.
    Returns:
        A Dash dcc.Tabs component with Data and Results tabs.
    """
    return dcc.Tabs(
        id="tabs",
        value='data-tab',
        style=tabs_styles,
        children=[
            dcc.Tab(
                value="data-tab",
                id="data-tab",
                label="Data",
                **all_tab_styles,
                children=[build_data_component(state)],
            ),
            dcc.Tab(
                value="results-tab",
                id="results-tab",
                label="Results",
                **all_tab_styles,
                children=[],
                disabled=True,
            ),
        ],
    )


def column_style(width: int) -> dict:
    """Generate an inline-block column style with a given percentage width.

    Used to arrange components side by side in a row layout.

    Args:
        width: Column width as a percentage of the parent container (0–100).
    Returns:
        A CSS style dictionary for use in a Dash component's style prop.
    """
    return {
        "width": f"{width}%",
        "display": "inline-block",
        "margin-left": 10,
        "verticalAlign": "middle",
    }


def get_group_sizes(
    object_data: pd.DataFrame,
    confounder: str,
    isolate_label: str = "Isolates and singletons",
) -> pd.DataFrame:
    """Compute the size of each group within a confounder.

    Groups objects by the specified confounder column and counts the number
    of objects in each group, sorted by size in descending order. Objects
    with an empty group assignment are relabeled.

    Args:
        object_data: DataFrame containing object metadata with one column
                     per confounder.
        confounder: Name of the confounder column to group by.
                    Defaults to 'family'.
        isolate_label: Display label for objects with no group assignment
                       (empty string). Defaults to 'Isolates and singletons'.
    Returns:
        DataFrame with columns [confounder, 'size', 'is_isolate'], sorted
        by size in descending order.
    """
    group_sizes = (
        object_data
        .groupby(confounder)
        .size()
        .reset_index(name="size")
        .sort_values("size", ascending=False)
    )

    group_sizes["is_isolate"] = group_sizes[confounder] == ""
    group_sizes.loc[group_sizes.is_isolate, confounder] = isolate_label

    return group_sizes


def build_data_component(state: AppState) -> html.Div:
    """Build the Data tab content showing a map and data exploration sif start_with_summarize:
        results_map = plot_summary_map(state, range_slider.value)
    else:
        results_map = plot_sample_map(state, sample_slider.value)ubtabs.

    Creates a layout with a map of all objects and two subtabs:
    - Confounder: a bar chart showing the number of objects per group in a confounder,
      with singletons (not assigned to any group) grouped together.
    - Features: a radio selector for coloring the map by feature value.

    Args:
        state: Current application state containing loaded data and figures.
    Returns:
        A Dash html.Div containing the data map and exploration subtabs.
    """
    group_sizes = get_group_sizes(state.object_data, confounder=state.confounder)
    group_size_graph = px.bar(
        group_sizes,
        x=state.confounder,
        y='size',
        orientation='v',
        color="is_isolate",
        color_discrete_sequence=[COLOR_NEUTRAL, COLOR_HIGHLIGHT],
    )
    group_size_graph.update_layout(showlegend=False, font={"size": 10})

    return html.Div([
        dcc.Graph(id="data_map", figure=state.data_fig),
        dcc.Tabs(
            id="data-subtabs",
            value='group-tab',
            style=tabs_styles,
            children=[
                dcc.Tab(
                    value="group-tab",
                    id="group-tab",
                    label=f"Groups by confounder {state.confounder}",
                    **all_tab_styles,
                    children=dcc.Graph(id='group-sizes', figure=group_size_graph),
                ),
                dcc.Tab(
                    value="feature-tab",
                    id="feature-tab",
                    label="Features",
                    **all_tab_styles,
                    children=dcc.RadioItems(
                        state.data.columns[5:],
                        id='feature-selector',
                        style={"font-size": 12},
                    ),
                ),
            ],
        ),
    ])


def build_results_components(
    state: AppState,
    start_with_summarize: bool = True,
) -> html.Div:
    """Build the Results tab content showing a map, trace plot and controls.

    Creates a layout with:
    - A sample slider for stepping through individual posterior samples
    - A range slider for selecting a subset of samples to summarise
    - A toggle switch for switching between sample and summary mode
    - A trace plot showing posterior log-likelihood over samples
    - A map showing either a single sample or a summary of the selected range
    - A button for downloading the map as an HTML file

    The sample slider and range slider are shown/hidden depending on the
    summarise toggle state.

    Args:
        state: Current application state containing loaded clusters and figures.
        start_with_summarize: Whether to start in summary mode. If True, the
                              range slider is shown and the summary map is
                              displayed. If False, the sample slider is shown
                              and a single sample map is displayed.
    Returns:
        A Dash html.Div containing all results components.
    """
    initialize_results_map(state)

    sample_slider = get_sample_slider(state)
    range_slider = get_summary_range_slider(state)
    trace_fig = plot_trace(state)

    if start_with_summarize:
        results_map = plot_summary_map(state, [0, state.n_samples])
    else:
        results_map = plot_sample_map(state, 0)

    return html.Div([
        html.Div(
            [
                html.P(
                    id="sample",
                    children="Sample number",
                    style={"font-size": 14, "text-indent": "10px"},
                ),
                sample_slider,
            ],
            id="slider_div",
            style={
                "width": "90%",
                "display": "none" if start_with_summarize else "inline-block",
            },
        ),
        html.Div(
            [
                html.P(
                    id="sample-range",
                    children="Sample range",
                    style={"font-size": 14, "text-indent": "10px"},
                ),
                range_slider,
            ],
            id="range_slider_div",
            style={
                "width": "90%",
                "display": "inline-block" if start_with_summarize else "none",
            },
        ),
        html.Div(
            [
                daq.BooleanSwitch(
                    id="summarize_switch",
                    label={"label": "Summarize samples", "style": {"font-size": 14}},
                    labelPosition="top",
                    on=start_with_summarize,
                )
            ],
            style={"width": "9%", "display": "inline-block"},
        ),
        dcc.Graph(
            id="trace",
            figure=trace_fig,
            style={"width": "93vw", "height": "160px"},
        ),
        dcc.Graph(
            id="map",
            figure=results_map,
            style={"width": "95vw", "margin-left": "1.8vw"},
        ),
        html.Div([
            html.Button("Download map as HTML", id="download-map-button"),
            dcc.Download(id="download-map"),
        ]),
    ], style={"textAlign": "center"})