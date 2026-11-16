# tests/test_polygons.py

import geopandas as gpd
import numpy as np
import pytest
from matplotlib import pyplot as plt
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, box

from sblot.config.config_io import (Config, DataConfig, ExperimentConfig, MapConfig,
                                    PlotsConfig, ResultsConfig, StyleConfig)
from sblot.core.utils import polygonal_part
from sblot.plots.map import add_object_polygons, load_object_polygons
from sbayes.load_data import Objects


# ── polygonal_part ────────────────────────────────────────────────────────────

def test_polygonal_part_keeps_polygons():
    poly = box(0, 0, 1, 1)
    assert polygonal_part(poly) is poly


def test_polygonal_part_drops_lines_from_collection():
    collection = GeometryCollection([
        box(0, 0, 1, 1),
        MultiPolygon([box(2, 2, 3, 3), box(4, 4, 5, 5)]),
        LineString([(0, 0), (1, 1)]),
    ])
    result = polygonal_part(collection)
    assert result.geom_type == "MultiPolygon"
    assert len(result.geoms) == 3


def test_polygonal_part_without_polygons():
    assert polygonal_part(LineString([(0, 0), (1, 1)])) is None
    assert polygonal_part(Point(0, 0)) is None
    assert polygonal_part(None) is None


# ── load_object_polygons / add_object_polygons ───────────────────────────────

@pytest.fixture
def objects():
    return Objects(
        id=["lang1", "lang2", "lang3"],
        locations=np.array([[10.0, 10.0], [20.0, 20.0], [30.0, 30.0]]),
        names=["Lang 1", "Lang 2", "Lang 3"],
    )


def make_config(tmp_path, polygons_path=None, polygon_id="glottocode", map_projection=None):
    features = tmp_path / "features.csv"
    features.write_text("id,x,y\n")
    feature_types = tmp_path / "feature_types.yaml"
    feature_types.write_text("{}\n")
    results = tmp_path / "results"
    results.mkdir(exist_ok=True)

    experiment = ExperimentConfig(
        data=DataConfig(features=features, feature_types=feature_types,
                        polygons=polygons_path, polygon_id=polygon_id),
        results=ResultsConfig(path_in=results),
        plots=PlotsConfig(map=MapConfig()),
    )
    style = StyleConfig()
    style.map.geo.map_projection = map_projection
    return Config(experiment=experiment, style=style)


@pytest.fixture
def polygons_file(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"glottocode": ["lang1", "lang1", "lang2", "other"]},
        geometry=[
            box(9, 9, 11, 11),
            box(12, 9, 13, 11),  # second part of lang1 -> merged
            GeometryCollection([box(19, 19, 21, 21), LineString([(19, 19), (21, 21)])]),
            box(0, 0, 1, 1),     # not an object -> ignored
        ],
        crs="EPSG:4326",
    )
    path = tmp_path / "polygons.geojson"
    gdf.to_file(path, driver="GeoJSON")
    return path


def test_no_polygons_configured(tmp_path, objects):
    config = make_config(tmp_path)
    assert config.experiment.data.polygons is None
    assert load_object_polygons(objects, config) is None


def test_load_object_polygons_aligned_with_objects(tmp_path, objects, polygons_file):
    config = make_config(tmp_path, polygons_file)
    polygons = load_object_polygons(objects, config)

    assert list(polygons.index) == ["lang1", "lang2", "lang3"]
    assert polygons["lang1"].geom_type == "MultiPolygon"
    assert polygons["lang1"].area == pytest.approx(6.0)
    assert polygons["lang2"].geom_type == "Polygon"
    assert polygons.isna().tolist() == [False, False, True]


def test_load_object_polygons_reprojects(tmp_path, objects, polygons_file):
    config = make_config(tmp_path, polygons_file, map_projection="epsg:3857")
    polygons = load_object_polygons(objects, config)
    # Web Mercator coordinates are in metres
    assert polygons["lang2"].bounds[2] > 1e6


def test_load_object_polygons_unknown_id_column(tmp_path, objects, polygons_file):
    config = make_config(tmp_path, polygons_file, polygon_id="does_not_exist")
    with pytest.raises(ValueError, match="glottocode"):
        load_object_polygons(objects, config)


@pytest.mark.parametrize("fill", [True, False])
def test_add_object_polygons_draws(tmp_path, objects, polygons_file, fill):
    config = make_config(tmp_path, polygons_file)
    polygons = load_object_polygons(objects, config)

    # 2 clusters, 4 samples, 3 objects: lang1 always in cluster 0, lang2 half of the time in cluster 1
    # shape: (n_samples, n_clusters, n_objects)
    clusters = np.zeros((4, 2, 3), dtype=bool)
    clusters[:, 0, 0] = True
    clusters[:2, 1, 1] = True

    fig, ax = plt.subplots()
    add_object_polygons(polygons, clusters, ["#ff0000", "#0000ff"], config, ax, fill=fill)

    facecolors = np.concatenate([c.get_facecolor() for c in ax.collections])
    if fill:
        # lang1: red with alpha = 1.0 * max_alpha, lang2: blue with alpha = 0.5 * max_alpha
        max_alpha = config.style.map.graphics.polygons.max_alpha
        assert any(np.allclose(fc, (1, 0, 0, max_alpha)) for fc in facecolors)
        assert any(np.allclose(fc, (0, 0, 1, 0.5 * max_alpha)) for fc in facecolors)
    else:
        assert np.all(facecolors[:, 3] == 0)
    plt.close(fig)
