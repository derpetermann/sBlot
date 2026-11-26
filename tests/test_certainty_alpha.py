from types import SimpleNamespace

import numpy as np
import pytest

from sblot.config.config_io import MapConfig, StyleConfig
from sblot.plots.map import get_certainty_alpha


def make_config(enabled=True, threshold=None, min_alpha=0.0):
    return SimpleNamespace(
        experiment=SimpleNamespace(plots=SimpleNamespace(map=MapConfig(
            certainty_alpha=enabled, min_posterior_probability=threshold))),
        style=StyleConfig(map={"graphics": {"clusters": {"min_certainty_alpha": min_alpha}}}),
    )


# Samples, shape (n_samples, n_clusters, n_objects). Object 0 is always at 0.7 in
# cluster 0; object 1 alternates between 0.4 and 1.0 in cluster 1 (mean 0.7).
CLUSTERS = np.array([
    [[0.7, 0.0], [0.1, 0.4]],
    [[0.7, 0.0], [0.1, 1.0]],
    [[0.7, 0.0], [0.1, 0.4]],
    [[0.7, 0.0], [0.1, 1.0]],
])


def test_disabled_returns_none():
    assert get_certainty_alpha(CLUSTERS, make_config(enabled=False)) is None


def test_share_of_samples_above_threshold():
    alpha = get_certainty_alpha(CLUSTERS, make_config(threshold=0.6))
    assert alpha == pytest.approx([1.0, 0.5])


def test_threshold_defaults_to_one_half():
    alpha = get_certainty_alpha(CLUSTERS, make_config(threshold=None))
    assert alpha == pytest.approx([1.0, 0.5])


def test_min_alpha_floor():
    alpha = get_certainty_alpha(CLUSTERS, make_config(threshold=0.6, min_alpha=0.2))
    assert alpha == pytest.approx([1.0, 0.6])


def test_binary_clusters_give_sample_frequency():
    clusters = np.zeros((4, 1, 1), dtype=bool)
    clusters[:3, 0, 0] = True
    alpha = get_certainty_alpha(clusters, make_config(threshold=0.9))
    assert alpha == pytest.approx([0.75])
