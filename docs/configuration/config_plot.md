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
| `path_in`  | string or list | *required* | Path to the results of an `sBayes` analysis, a parent folder with one subfolder per experiment, or a list of such paths (see below) |
| `path_out` | string | `{path_in}_plots` | Directory where generated plots will be saved (for a list: common parent of all paths + `_plots`) |
| `burn_in`  | float  | `0.2`             | Fraction of samples to discard as burn-in (0.0–1.0)                      |
| `thinning` | int    | `1`               | Keep every *n*th sample to reduce memory usage                           |
| `combine_runs` | bool | `true`          | Concatenate all runs of a model; if `false`, each run is plotted separately with the run id appended to the file names (e.g. `pie_plot_K3_0.pdf`) |
| `cluster_reference` | string | `null` | Cluster reference table (`cluster_reference_K{K}.tsv`) or a folder of such tables to align the clusters to (see below) |
| `write_cluster_reference` | bool | `false` | Write missing reference tables to the `cluster_reference` folder, from the first experiment with that K |


### Multiple experiments
An *experiment* is the results folder of one `sBayes` setup (e.g. one set of model settings). `path_in` can point to:
- a model folder containing `samples_*.h5` files (the experiment is named after its parent folder),
- an experiment folder with one subfolder per model (e.g. `K1`, `K2`, ...),
- a parent folder with one subfolder per experiment,
- a list of any of the above.

```yaml
results:
  path_in:
    - results/experiment_a
    - results/experiment_b
```

When there are several experiments, the plots of each experiment are saved to their own subfolder
(`{path_out}/{experiment}/...`), and the `loo` plot compares all experiments.

### Aligning clusters across experiments
Cluster labels are arbitrary, so different experiments (or separately plotted runs) can find the
same clusters under different labels and therefore different colours. With `cluster_reference`,
the clusters of every model are aligned to a reference table with the same K, so that colours and
cluster order stay the same across experiments and across plotting sessions (e.g. when an
experiment is added later, only the new experiment needs to be plotted).

The reference is a TSV table per K, `cluster_reference_K{K}.tsv`, with the mean membership of each
object (rows) in each cluster (columns):

```
object  id      name      a0     a1
0       abcd1   Lang A    0.912  0.003
1       efgh2   Lang B    0.004  0.871
...
```

- the **column order** sets the cluster order (`Z1`, `Z2`, ... and their colours),
- the **column names** set the cluster names (e.g. in the preferences plots),
- objects are matched by `id` if present, otherwise by the `object` index.

The table can be edited by hand, e.g. to reorder the clusters for more contrast between
neighbouring clusters on a map, or to roughly match the clusters across different K.

There are two ways to create the tables:
- set `write_cluster_reference: true`: sBlot writes a table for each K that has none yet, from the
  first experiment in `path_in` with that K. Existing tables are never overwritten.
- run `sbayesAlignClusters <results> --write-reference [DIR] --features <features.csv>` in sBayes,
  which uses the same reference run as for the aligned stats files.

```yaml
results:
  path_in: results
  cluster_reference: results/cluster_reference
  write_cluster_reference: true
```

## Data (`data`)
Specify the input data used in the analysis, including feature definitions and spatial reference information.

| Key             | Type   | Default      | Description                                                                                     |
|-----------------|--------|--------------|-------------------------------------------------------------------------------------------------|
| `features`      | string | *required*   | Path to the features CSV file                                                                   |
| `feature_types` | string | *required*   | Path to the `feature_types.yaml` file defining the type of each feature                         |
| `projection`    | string | `epsg:4326`  | Coordinate reference system (CRS) of the input data (PROJ string or EPSG). For `map` plots only |
| `polygons`      | string | `null`       | Optional GeoJSON file with a (multi-)polygon per object, e.g. language areas. For `map` plots only |
| `polygon_id`    | string | `glottocode` | GeoJSON feature property that is matched against the `id` column of the features CSV          |

Note that the projection might differ from the `map_projection` in `config_style.yaml`.

Polygons are expected in longitude/latitude (as required by the GeoJSON standard),
regardless of `projection`. Several features with the same id are merged, and only
the polygonal parts of `GeometryCollection`s are used. Objects without a polygon are
shown as points only.

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
| `chart_type` | string | `pie` | Panel type per object: `pie` = share of samples per cluster, `kde` or `histogram` = distribution of each cluster's membership across samples |
| `confounder` | string | `null` | Confounder whose group is shown beneath each object name, e.g. `family`. `null` = none |
| `group_by_cluster` | boolean | `false` | Arrange the panels in one row per cluster, holding the objects whose median membership in that cluster is at least `group_by_cluster_threshold`, sorted by that median. Objects can appear in several rows |
| `group_by_cluster_threshold` | float | `0.5` | Minimum median cluster membership for an object to appear in a cluster's row |

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
| `confounder_overlap_only`   | bool    | `true`    | Only overlay confounder groups that contain objects shown in a cluster. `false` = overlay all groups        |
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
