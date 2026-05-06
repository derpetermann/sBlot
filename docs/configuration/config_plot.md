[← Back to documentation](../index.md)
# Plot configuration

The **`config_plot.yaml`** file specifies the input data and results of 
an `sBayes` analysis for visualisation, along with the plots to generate and the 
analytical tasks to perform for each plot.

It consists of three main sections:
- [**results**](#results-results): file paths to the outputs of an `sBayes` analysis  
- [**data**](#data-data): file paths to the empirical data used in the analysis  
- [**plots**](#plots-plots): definitions of the plots to generate and the associated analytical tasks  

## Results (`results`)
Specify the input and output paths for an `sBayes` run, along with parameters controlling how posterior samples are processed.

| Key        | Type   | Default           | Description                                                              |
|------------|--------|-------------------|--------------------------------------------------------------------------|
| `path_in`  | string | *required*        | Path to the results files (clusters and stats) from an `sBayes` analysis |
| `path_out` | string | `{path_in}_plots` | Directory where generated plots will be saved                            |
| `burn_in`  | float  | `0.2`             | Fraction of samples to discard as burn-in (0.0–1.0)                      |
| `thinning` | int    | `1`               | Keep every *n*th sample to reduce memory usage                           |


## Data (`data`)
Specify the input data used in the analysis, including feature definitions and spatial reference information.

| Key             | Type   | Default      | Description                                                                                     |
|-----------------|--------|--------------|-------------------------------------------------------------------------------------------------|
| `features`      | string | *required*   | Path to the features CSV file                                                                   |
| `feature_types` | string | *required*   | Path to the `feature_types.yaml` file defining the type of each feature                         |
| `projection`    | string | `epsg:4326`  | Coordinate reference system (CRS) of the input data (PROJ string or EPSG). For `map` plots only |

Note that the projection might differ from the `map_projection` in `config_style.yaml`.

## Plots (`plots`)

Defines which plots to generate and their configuration.

| Key           | Description                                                                                         |
|---------------|-----------------------------------------------------------------------------------------------------|
| `weights`     | Weight plots showing posterior weight distributions                                                 |
| `preferences` | Preference plots showing the posterior distribution of features in the clusters and the confounders |
| `pies`        | Pie chart plots showing cluster membership per object                                               |
| `loo`         | Loo plots compare models with different numbers of clusters.                                        |
| `map`         | Posterior map showing cluster assignments in geographic space                                       |

The sections below describe each plot type in more detail. 

### Weight plots (`plots.weights`)
Weight plots show the posterior weight distributions.

| Key        | Type         | Required | Default | Description                                    |
|------------|--------------|----------|---------|------------------------------------------------|
| `features` | list[string] | No       | `[]`    | Features to plot. Empty = plot all features    |

### Preference plots (`plots.preferences`)
Preference plots show the posterior distribution of features in the clusters and each group of the confounders.

| Key          | Type         | Default    | Description                                                                 |
|--------------|--------------|------------|-----------------------------------------------------------------------------|
| `features`   | list[string] | `[]`       | Feature names to plot. Empty = plot all features                            |
| `components` | list         | `[]`       | Components to plot. Empty = plot all components.                            |
| `reference`  | string       | `null`     | Reference component shown as overlay behind each plot. `null` = no overlay  |

#### `plots.preferences.components`
Each entry in `components` has the following keys. Only relevant when `components` is provided.

| Key         | Type         | Default    | Description                                                                              |
|-------------|--------------|------------|------------------------------------------------------------------------------------------|
| `component` | string       | *required* | Component name; either a confounder (e.g. `family`, `universal`) or `clusters`           |
| `groups`    | list[string] | `[]`       | Groups to plot within the component. Empty = plot all groups e.g. `["Turkic", "Altaic"]` |


### Pie plots (`plots.pies`)
Pie chart plots show the posterior cluster membership per object.

| Key       | Type    | Default | Description                                                        |
|-----------|---------|---------|--------------------------------------------------------------------|
| `enabled` | boolean | `false` | Whether to generate pie charts. Set to `true` to enable this plot  |

### Loo plots (`plots.loo`)
PSIS-LOO plots compare the posterior support for different models.

| Key       | Type    | Default | Description                                                              |
|-----------|---------|---------|--------------------------------------------------------------------------|
| `enabled` | boolean | `false` | Whether to generate the PSIS-LOO plot. Set to `true` to enable this plot |


### Maps (`plots.map`)
The posterior maps show cluster assignments in geographic space.

| Key                         | Type    | Default   | Description                                                                                                 |
|-----------------------------|---------|-----------|-------------------------------------------------------------------------------------------------------------|
| `type`                      | string  | `line`    | Map type: `line` = objects in clusters connected with a graph, `pie` = pie charts, `idw` = interpolated map |
| `plot_confounder`           | string  | `null`    | Confounder to overlay on the map as alpha shapes e.g. `family`. `null` = no overlay                         |
| `labels`                    | string  | `all`     | Which objects to label: `all`, `in_cluster` or `none`                                                       |
| `min_posterior_probability` | float   | `null`    | Minimum posterior probability for an object to appear in the cluster. `null` = show all objects             |
| `per_cluster`               | boolean | `false`   | Generate one map per cluster instead of all clusters combined                                               |
| `line`                      | dict    | —         | Line map settings. Only relevant when `type` is `line`. See below                                           |
| `idw`                       | dict    | —         | IDW map settings. Only relevant when `type` is `idw`. See below                                             |

#### `plots.map.line`
Line map settings. 

| Key     | Type   | Default   | Description                                                                         |
|---------|--------|-----------|-------------------------------------------------------------------------------------|
| `graph` | string | `gabriel` | Graph type connecting objects within a cluster: `gabriel`, `delaunay` or `complete` |

#### `plots.map.idw`
Settings for a map with inverse distance weighted interpolation.

| Key                 | Type  | Default | Description                                                      |
|---------------------|-------|---------|------------------------------------------------------------------|
| `resolution`        | int   | `50000` | Grid cell size in map CRS units. Smaller = finer grid, slower    |
| `power`             | int   | `2`     | Distance decay power. Higher = more influence from nearby points |
| `background_weight` | float | `1.0`   | Weight of background color in areas far from any data point      |
