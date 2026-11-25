from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib import colors
from matplotlib.patches import Rectangle, Wedge
from sbayes.load_data import Confounder

import sblot.plots.pies as pies_module
from sblot.config.config_io import GlobalConfig, PiesConfig
from sblot.plots.pies import plot_pies

RED, BLUE = "#ff0000", "#0000ff"

# Cluster samples, shape (n_samples, n_clusters, n_objects): object 0 mostly
# in cluster 0, object 1 mostly in cluster 1, object 2 in neither.
CLUSTERS = np.array([
    [[0.8, 0.2, 0.1], [0.1, 0.7, 0.1]],
    [[0.9, 0.1, 0.2], [0.0, 0.8, 0.0]],
    [[0.7, 0.3, 0.1], [0.2, 0.6, 0.2]],
])


def render(tmp_path, monkeypatch, plots: dict | None = None, style: dict | None = None,
           confounders: dict | None = None):
    """Run plot_pies on the synthetic clusters and return the figure."""
    n_objects = CLUSTERS.shape[2]
    config = SimpleNamespace(
        experiment=SimpleNamespace(
            plots=SimpleNamespace(pies=PiesConfig(**(plots or {}))),
            results=SimpleNamespace(path_out=tmp_path),
        ),
        style=SimpleNamespace(
            pies=PiesConfig(**(style or {"output": {"n_columns": 3}})),
            global_=GlobalConfig(cluster_colors=[RED, BLUE], format="png", resolution=20),
        ),
    )
    objects = SimpleNamespace(names=[f"site {i}" for i in range(n_objects)],
                              indices=np.arange(n_objects))
    data = (objects, None, confounders or {})
    results = SimpleNamespace(clusters=CLUSTERS, n_clusters=CLUSTERS.shape[1])

    captured = {}
    monkeypatch.setattr(pies_module.plt, "close", lambda fig: captured.setdefault("fig", fig))
    plot_pies(results, data, config, verbose=False)
    return captured["fig"]


def wedge_colors(ax):
    return [p.get_facecolor() for p in ax.patches if isinstance(p, Wedge)]


def test_pie_highlights_main_cluster(tmp_path, monkeypatch):
    fig = render(tmp_path, monkeypatch)
    other = colors.to_rgba("#808080", alpha=0.35)
    first, second = fig.axes[0], fig.axes[1]
    assert np.allclose(wedge_colors(first)[0], colors.to_rgba(RED))
    assert np.allclose(wedge_colors(first)[1], other)
    assert np.allclose(wedge_colors(second)[0], other)
    assert np.allclose(wedge_colors(second)[1], colors.to_rgba(BLUE))
    assert (tmp_path / "pies" / "pie_plot_K2.png").exists()


def test_pie_without_highlight_keeps_cluster_colors(tmp_path, monkeypatch):
    style = {"output": {"n_columns": 3}, "highlight": {"enabled": False}}
    fig = render(tmp_path, monkeypatch, style=style)
    assert np.allclose(wedge_colors(fig.axes[0])[1], colors.to_rgba(BLUE))


@pytest.mark.parametrize("chart_type", ["kde", "histogram"])
def test_distribution_charts_honor_y_max(tmp_path, monkeypatch, chart_type):
    style = {"output": {"n_columns": 3}, "distribution": {"y_max": 7.5, "n_bins": 5}}
    fig = render(tmp_path, monkeypatch, plots={"chart_type": chart_type}, style=style)
    ax = fig.axes[0]
    assert ax.get_ylim()[1] == pytest.approx(7.5)
    if chart_type == "kde":
        assert len(ax.lines) >= 2
    else:
        bars = [p for p in ax.patches if isinstance(p, Rectangle)]
        assert len(bars) == 2 * 5


def test_group_by_cluster_rows(tmp_path, monkeypatch):
    plots = {"group_by_cluster": True, "group_by_cluster_threshold": 0.5}
    fig = render(tmp_path, monkeypatch, plots=plots)
    # One row per cluster with one object each: object 0 in row 0, object 1 in row 1
    assert len(fig.axes) == 2
    texts = [[t.get_text() for t in ax.texts] for ax in fig.axes]
    assert "site 0" in texts[0] and "site 1" in texts[1]


def test_confounder_label_beneath_name(tmp_path, monkeypatch):
    family = Confounder(
        name="family",
        group_assignment=np.array([[True, False, False], [False, True, False]]),
        group_names=["Indo-European", "Uralic"],
    )
    fig = render(tmp_path, monkeypatch, plots={"confounder": "family"},
                 confounders={"family": family})
    assert "Indo-\nEuropean" in [t.get_text() for t in fig.axes[0].texts]
    assert "Uralic" in [t.get_text() for t in fig.axes[1].texts]
    labels = [t.get_text() for t in fig.axes[2].texts if t.get_text()]
    assert labels == ["3", "site 2"]  # no group: only index and name


def test_unknown_confounder_raises(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="Unknown confounder"):
        render(tmp_path, monkeypatch, plots={"confounder": "family"})
