[← Back to documentation](index.md)

# Creating plots

Users have two options to generate plots using the `sBlot` package: either from the command line or through a Python script, e.g., as part of a Jupyter Notebook.

## Command line

The simplest way to generate all plots at once is to run `sblot` passing it the file path to a `config_plot.yaml` configuration file:

`sblot -c config_plot.yaml`

All plots specified in `config_plot.yaml` are generated automatically using the default style configuration.
To control which plots are generated, add or remove sections from the `plots` block in `config_plot.yaml`.
To use a custom style configuration, also pass a custom `config_style.yaml` file:

`sblot -c config_plot.yaml -s config_style.yaml`

## Python script

Users can use the Python API directly to generate only specific plots, inspect intermediate results, or integrate plots into a larger workflow.

    from sblot.config.config_io import load_config, read_data, read_results

    config = load_config("config_plot.yaml", "config_style.yaml")
    data = read_data(config)
    all_models = list(read_results(config))

The configuration is loaded from `config_plot.yaml` and `config_style.yaml`, combining analytical settings and visual style into a single `config` object. The data (objects, features and confounders) and all MCMC results are then read from the paths specified in the `config_plot.yaml` file, with posterior samples aligned across runs and burn-in applied automatically.

### Weight plots

[Weight plots](plots/weights.md) visualise the posterior distribution of areal, universal and inheritance weights for each feature.

    from sblot.plots.weights import plot_weights

    for model in all_models:
        if config.experiment.plots.weights:
            plot_weights(model.results, config)

### Preference plots

[Preference plots](plots/preferences.md) show the posterior distribution of feature state preferences for each component (cluster effect and confounders). One grid of panels is generated per component.

    from sblot.plots.preferences import plot_preferences

    for model in all_models:
        if config.experiment.plots.preferences:
            plot_preferences(model.results, config)

### Pie plots

[Pie plots](plots/pies.md) show the posterior cluster membership for each object. Each slice represents the fraction of posterior samples in which the object was assigned to a given cluster.

    from sblot.plots.pies import plot_pies

    for model in all_models:
        if config.experiment.plots.pies:
            plot_pies(model.results, data, config)

### Maps

[Maps](plots/map.md) show the geographic distribution of posterior cluster assignments. Three map types are available: `line`, `pie` and `idw`. Set `type` in `config_plot.yaml` to switch between them.

    from sblot.plots.map import plot_maps

    for model in all_models:
        if config.experiment.plots.map:
            plot_maps(model.results, data, config)

To generate one map per cluster in addition to a combined map, set `per_cluster: true` in `config_plot.yaml`.


### LOO plots

[PSIS-LOO model comparison plots](plots/loo.md) compare models with different numbers of clusters. Requires likelihood files (`likelihood_*.h5`) in the results directory.
    
    from sblot.plots.loo import plot_loo

    if config.experiment.plots.loo:
        plot_loo(all_models, config)