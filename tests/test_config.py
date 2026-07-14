# tests/test_config.py

from pathlib import Path
import pytest
from pydantic import ValidationError
from sblot.config.config_io import (load_config, ResultsConfig, MapConfig,
                                    WeightsLabelConfig, find_confounder_names)

# Path to test files
TEST_DIR = Path(__file__).parent
CONFIG_PLOT = TEST_DIR / "data" / "config_plot.yaml"
CONFIG_STYLE = TEST_DIR / "data" / "config_style.yaml"
FEATURES_CSV = TEST_DIR / "data" / "features.csv"
FEATURE_TYPES = TEST_DIR / "data" / "feature_types.yaml"
RESULTS_DIR = TEST_DIR / "data" / "results"


# ── Config loading ────────────────────────────────────────────────────────────

def test_load_config_valid():
    """Test that a valid config loads correctly and values match the config files."""
    config = load_config(CONFIG_PLOT, CONFIG_STYLE)
    assert config.experiment.results.burn_in == 0.2
    assert config.experiment.data.projection == "epsg:4326"
    assert config.style.global_.format == "png"


def test_relative_paths_resolved():
    """Test that relative paths are resolved relative to the config file location."""
    config = load_config(CONFIG_PLOT, CONFIG_STYLE)
    assert config.experiment.data.features.is_absolute()
    assert config.experiment.data.feature_types.is_absolute()
    assert config.experiment.results.path_in.is_absolute()


def test_path_out_default():
    """Test that path_out defaults to path_in + '_plots' when not set."""
    config = load_config(CONFIG_PLOT, CONFIG_STYLE)
    expected = Path(str(config.experiment.results.path_in) + "_plots")
    assert config.experiment.results.path_out == expected


# ── ResultsConfig validators ──────────────────────────────────────────────────

def test_invalid_burn_in_above_one():
    """Test that burn_in >= 1.0 raises a ValidationError."""
    with pytest.raises(ValidationError):
        ResultsConfig(path_in=str(RESULTS_DIR), burn_in=1.0)


def test_invalid_burn_in_below_zero():
    """Test that burn_in <= 0.0 raises a ValidationError."""
    with pytest.raises(ValidationError):
        ResultsConfig(path_in=str(RESULTS_DIR), burn_in=0.0)


# ── MapConfig validators ──────────────────────────────────────────────────────

def test_invalid_min_posterior_probability():
    """Test that min_posterior_probability outside (0, 1) raises a ValidationError."""
    with pytest.raises(ValidationError):
        MapConfig(min_posterior_probability=1.5)


def test_map_type_all_expands():
    """Test that type='all' expands to all map types."""
    config = MapConfig(type="all")
    assert set(config.type) == {"pie", "line", "idw"}


# ── find_confounder_names ─────────────────────────────────────────────────────

def test_find_confounder_names_returns_correct_names():
    """Test that confounder names are correctly identified from the CSV."""
    confounders = find_confounder_names(FEATURES_CSV, FEATURE_TYPES)
    assert "family" in confounders


def test_find_confounder_names_excludes_metadata():
    """Test that metadata columns are excluded from confounder names."""
    confounders = find_confounder_names(FEATURES_CSV, FEATURE_TYPES)
    for col in ["id", "x", "y", "name"]:
        assert col not in confounders


def test_find_confounder_names_excludes_features():
    """Test that feature columns are excluded from confounder names."""
    import yaml
    with open(FEATURE_TYPES) as f:
        feature_types = yaml.safe_load(f)
    confounders = find_confounder_names(FEATURES_CSV, FEATURE_TYPES)
    for feature in feature_types.keys():
        assert feature not in confounders


# ── read_results folder structure ─────────────────────────────────────────────

def test_read_results_flat_structure(tmp_path):
    """Test that flat results directory (files directly in path_in) is detected correctly."""
    config = load_config(CONFIG_PLOT, CONFIG_STYLE)
    models = list(config.read_results())
    assert len(models) > 0
    assert models[0].k > 0


def test_read_results_empty_directory_raises(tmp_path):
    """Test that an empty results directory raises FileNotFoundError."""
    config = load_config(CONFIG_PLOT, CONFIG_STYLE)
    config.experiment.results.path_in = tmp_path
    with pytest.raises(FileNotFoundError):
        list(config.read_results())


def test_read_results_sorted_by_k(tmp_path):
    """Test that models in nested structure are sorted by K correctly."""
    config = load_config(CONFIG_PLOT, CONFIG_STYLE)
    models = list(config.read_results())
    ks = [m.k for m in models]
    assert ks == sorted(ks)


# ── WeightsLabelConfig.resolve_names ─────────────────────────────────────────

def test_resolve_names_explicit():
    """Test that explicit names are returned when provided."""
    from unittest.mock import MagicMock
    results = MagicMock()
    results.confounders = ["family", "universal"]
    config = WeightsLabelConfig(names=["C", "F", "U"])
    assert config.resolve_names(results) == ["C", "F", "U"]


def test_resolve_names_inferred():
    """Test that names are inferred from component names when not provided."""
    from unittest.mock import MagicMock
    results = MagicMock()
    results.confounders = ["family", "universal"]
    config = WeightsLabelConfig()
    labels = config.resolve_names(results)
    assert labels == ["C", "F", "U"]


def test_resolve_names_warns_on_duplicate():
    """Test that a warning is raised when two inferred labels are identical."""
    from unittest.mock import MagicMock
    results = MagicMock()
    results.confounders = ["family", "french"]  # both start with F
    config = WeightsLabelConfig()
    with pytest.warns(UserWarning):
        config.resolve_names(results)