from pathlib import Path
import pytest
from sblot.config.config_io import load_config
from sblot.plots.weights import plot_weights
from sblot.plots.preferences import plot_preferences
from sblot.plots.pies import plot_pies
from sblot.plots.map import plot_maps
from sblot.plots.loo import plot_loo

TEST_DIR = Path(__file__).parent
CONFIG_PLOT = TEST_DIR / "data" / "config_plot.yaml"
CONFIG_STYLE = TEST_DIR / "data" / "config_style.yaml"


@pytest.fixture
def config():
    return load_config(CONFIG_PLOT, CONFIG_STYLE)

@pytest.fixture
def all_models(config):
    return list(config.read_results())

@pytest.fixture
def data(config):
    return config.read_data()


def test_weights(config, all_models, tmp_path):
    """Test that weight plot creates a plot."""
    for model in all_models:
        plot_weights(model.results, config)
    output = config.experiment.results.path_out / "weights"
    assert any(output.glob("*.png"))

def test_preferences(config, all_models, tmp_path):
    """Test that preference plot creates a plot."""
    for model in all_models:
        plot_preferences(model.results, config)
    output = config.experiment.results.path_out / "preferences"
    assert any(output.glob("*.png"))

def test_pies(config, all_models, data, tmp_path):
    """Test that pie plot creates a plot."""
    for model in all_models:
        plot_pies(model.results, data, config)
    output = config.experiment.results.path_out / "pies"
    assert any(output.glob("*.png"))

def test_map(config, all_models, data, tmp_path):
    """Test that map plot creates a plot."""
    for model in all_models:
        plot_maps(model.results, data, config)
    output = config.experiment.results.path_out / "map"
    assert any(output.glob("*.png"))

def test_loo(config, all_models, tmp_path):
    """Test that loo plot creates a plot."""
    plot_loo(all_models, config)
    output = config.experiment.results.path_out / "loo"
    assert any(output.glob("*.png"))