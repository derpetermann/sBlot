# sBlot

sBlot is a Python library for visualising the results of a [sBayes](https://github.com/NicoNeureiter/sBayes) analysis. 
It provides static plots (weights, preferences per component, pie charts, maps and LOO model comparison) as well as an interactive browser-based explorer for inspecting posterior samples.

For detailed instructions on configuration and individual plot types, see the [documentation](https://derpetermann.github.io/sBlot/).

## Installation

Install the latest release from PyPI:

```
pip install sblot
```

To include the interactive explorer:

```
pip install sblot[interactive]
```

To include LOO model comparison plots:

```
pip install sblot[loo]
```

To install all optional dependencies:

```
pip install sblot[all]
```

To install the development version directly from GitHub:

```
pip install git+https://github.com/derpetermann/sBlot.git
```

## Quick start

### Command line

Generate all plots specified in `config_plot.yaml`:

```
sblot -c config_plot.yaml
```

To use a custom style configuration:

```
sblot -c config_plot.yaml -s config_style.yaml
```

To initialise a new experiment directory with example configuration files:

```
sblot --init my_experiment/
```

### Python script

```
from sblot.config_io import load_config
from sblot.plots.weights import plot_weights_grid
from sblot.plots.preferences import plot_preferences_grid
from sblot.plots.pies import plot_pies
from sblot.plots.map import plot_maps
from sblot.plots.loo import plot_loo

config = load_config("config_plot.yaml", "config_style.yaml")
data = config.read_data()
all_models = list(config.read_results())

for model in all_models:
    plot_weights(model.results, config)
    plot_preferences(model.results, config)
    plot_pies(model.results, data, config)
    plot_maps(model.results, data, config)

plot_loo(all_models, config)
```

### Interactive explorer

In the command line:
```
sblot-interactive --conf family -d data/features.csv
```
Then open the interactive map in your browser at the address shown in the command line.

## License

sBlot is released under the [GNU General Public License v3](LICENSE).