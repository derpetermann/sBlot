[← Back to documentation](../index.md)

# Style configuration
The **`config_style.yaml`** file defines the graphical styling for all plots, including colors, fonts, and output settings.

## Global settings (`global`)
The global settings apply to all plots and define the output format, resolution, and cluster colors used throughout the visualisations.

| Key               | Type         | Default  | Description                                                                                                       |
|-------------------|--------------|----------|-------------------------------------------------------------------------------------------------------------------|
| `format`          | string       | `pdf`    | Output file format for all plots: `pdf`, `png` or `svg`                                                           |
| `resolution`      | int          | `300`    | Output resolution in DPI. Typical values: `300` (print), `96` (screen)                                            |
| `cluster_colors`  | list[string] | `[]`     | Hex color strings for each cluster. Used consistently across all plots. Empty = auto-generate colors              |

## Weight plots (`weights`)
Style settings for weight plots.

| Key                          | Type    | Default   | Description                                           |
|------------------------------|---------|-----------|-------------------------------------------------------|
| `simplex`                    | dict    | —         | Style settings for the probability simplex. See below |
| `mean`                       | dict    | —         | Style settings for the mean weight marker. See below  |
| `legend`                     | dict    | —         | Style settings for the legend. See below              |
| `output`                     | dict    | —         | Output settings for the grid layout. See below        |

### `weights.simplex`
Controls the appearance of the probability simplex.

| Key             | Type   | Default   | Description                                                                                                                           |
|-----------------|--------|-----------|---------------------------------------------------------------------------------------------------------------------------------------|
| `color`         | string | `#005570` | Color of the density curve and border for models with two components. For more components a cubehelix color map is used automatically |
| `border_width`  | float  | `0.2`     | Line width of the triangular simplex border                                                                                           |
| `padding`       | float  | `0.1`     | Padding around the simplex in axis units                                                                                              |
| `label_stretch` | float  | `1.15`    | Stretch factor for corner label positions (>1 moves labels outward)                                                                   |

### `weights.mean`
Controls the marker shown at the mean weight position inside the simplex.

| Key      | Type    | Default   | Description                                 |
|----------|---------|-----------|---------------------------------------------|
| `show`   | boolean | `true`    | Whether to plot the mean weight as a marker |
| `color`  | string  | `#ed1696` | Color of the mean marker                    |
| `size`   | int     | `10`      | Size of the mean marker in points²          |
| `marker` | string  | `o`       | Matplotlib marker style                     |

### `weights.legend`
Controls the legend elements shown in each simplex panel.

| Key             | Type | Default | Description                                                    |
|-----------------|------|---------|----------------------------------------------------------------|
| `title`         | dict | —       | Style settings for the feature name title. See below           |
| `corner_labels` | dict | —       | Style settings for the corner labels of the simplex. See below |


#### `weights.legend.title`
Controls the feature name displayed above each simplex panel.

| Key          | Type    | Default | Description                                    |
|--------------|---------|---------|------------------------------------------------|
| `add`        | boolean | `true`  | Whether to add the feature name as a title     |
| `font_size`  | int     | `6`     | Font size of the title                         |
| `position.x` | float   | `0`     | Horizontal position in axes coordinates (0–1)  |
| `position.y` | float   | `1`     | Vertical position in axes coordinates (0–1)    |

#### `weights.legend.corner_labels`
Controls the component labels shown for each corner of the simplex.

| Key         | Type    | Default | Description                                                              |
|-------------|---------|---------|--------------------------------------------------------------------------|
| `add`       | boolean | `true`  | Whether to add corner labels                                             |
| `font_size` | int     | `6`     | Font size of the corner labels. Labels are inferred from component names |

### `weights.output`
Controls the size and spacing of the simplex panel grid.

| Key                  | Type  | Default | Description                                   |
|----------------------|-------|---------|-----------------------------------------------|
| `width_subplot`      | float | `2`     | Width of each simplex panel in inches         |
| `height_subplot`     | float | `2`     | Height of each simplex panel in inches        |
| `n_columns`          | int   | `5`     | Number of columns in the simplex grid         |
| `spacing_horizontal` | float | `0.1`   | Horizontal spacing between panels (wspace)    |
| `spacing_vertical`   | float | `0.1`   | Vertical spacing between panels (hspace)      |

## Preference plots (`preferences`)
Style settings for preference plots.

| Key               | Type   | Default   | Description                                                                                                                         |
|-------------------|--------|-----------|-------------------------------------------------------------------------------------------------------------------------------------|
| `color`           | string | `#005570` | Color of the density curve and border for features with two states. For more components a cubehelix color map is used automatically |
| `reference_color` | string | `#b0b0b0` | Color of the reference component overlay                                                                                            |
| `legend`          | dict   | —         | Style settings for the legend. See below                                                                                            |
| `output`          | dict   | —         | Output settings for the grid layout. See below                                                                                      |

### `preferences.legend`
Controls the legend elements shown in each simplex panel.

| Key      | Type | Default | Description                                            |
|----------|------|---------|--------------------------------------------------------|
| `labels` | dict | —       | Style settings for the state labels at simplex corners |
| `title`  | dict | —       | Style settings for the feature name title              |

#### `preferences.legend.labels`
Controls the state labels shown for each corner of the simplex.

| Key         | Type    | Default | Description                              |
|-------------|---------|---------|------------------------------------------|
| `add`       | boolean | `true`  | Whether to add state labels              |
| `font_size` | int     | `4`     | Font size of the state labels            |

#### `preferences.legend.title`
Controls the feature name displayed above each simplex panel.

| Key          | Type    | Default | Description                                   |
|--------------|---------|---------|-----------------------------------------------|
| `add`        | boolean | `true`  | Whether to add the feature name as a title    |
| `font_size`  | int     | `6`     | Font size of the title                        |
| `position.x` | float   | `0`     | Horizontal position in axes coordinates (0–1) |
| `position.y` | float   | `1`     | Vertical position in axes coordinates (0–1)   |

### `preferences.output`
Controls the size and spacing of the simplex panel grid.

| Key                  | Type  | Default | Description                            |
|----------------------|-------|---------|----------------------------------------|
| `width_subplot`      | float | `3`     | Width of each simplex panel in inches  |
| `height_subplot`     | float | `3`     | Height of each simplex panel in inches |
| `n_columns`          | int   | `5`     | Number of columns in the simplex grid  |
| `spacing_horizontal` | float | `0.2`   | Horizontal spacing between panels      |
| `spacing_vertical`   | float | `0.3`   | Vertical spacing between panels        |

## Pie plots (`pies`)
Style settings for pie chart plots showing cluster membership per object.

| Key      | Type | Default | Description                                      |
|----------|------|---------|--------------------------------------------------|
| `label`  | dict | —       | Style settings for object labels                 |
| `pie`    | dict | —       | Style settings for individual pie charts         |
| `axes`   | dict | —       | Axes limits and label positions                  |
| `output` | dict | —       | Output settings for the grid layout              |

### `pies.label`
Controls the appearance of object labels next to each pie chart.

| Key                | Type | Default | Description                                                           |
|--------------------|------|---------|-----------------------------------------------------------------------|
| `index_size`       | int  | `15`    | Font size of the object index number                                  |
| `name_size`        | int  | `15`    | Font size of the object name                                          |
| `max_label_length` | int  | `10`    | Character threshold above which long labels are broken into two lines |

### `pies.pie`
Controls the appearance of individual pie charts.

| Key                | Type   | Default     | Description                                   |
|--------------------|--------|-------------|-----------------------------------------------|
| `radius`           | float  | `15`        | Pie chart radius in axis units                |
| `no_cluster_color` | string | `lightgrey` | Color for objects not assigned to any cluster |

### `pies.axes`
Controls the axes limits and label positions within each pie panel.

| Key       | Type  | Default | Description                                                |
|-----------|-------|---------|------------------------------------------------------------|
| `x_min`   | float | `0`     | Minimum x axis limit                                       |
| `x_max`   | float | `160`   | Maximum x axis limit                                       |
| `y_min`   | float | `-10`   | Minimum y axis limit                                       |
| `y_max`   | float | `10`    | Maximum y axis limit                                       |
| `index_x` | float | `0.20`  | Horizontal position of the index label in axes coordinates |
| `name_x`  | float | `0.25`  | Horizontal position of the name label in axes coordinates  |
| `label_y` | float | `0.5`   | Vertical position of both labels in axes coordinates       |

### `pies.output`
Controls the size and spacing of the pie chart grid.

| Key                  | Type  | Default | Description                             |
|----------------------|-------|---------|-----------------------------------------|
| `width`              | float | `4`     | Width of each pie panel in inches       |
| `height`             | float | `2`     | Height of each pie panel in inches      |
| `n_columns`          | int   | `10`    | Number of columns in the pie chart grid |
| `spacing_horizontal` | float | `0.01`  | Horizontal spacing between panels       |
| `spacing_vertical`   | float | `0.01`  | Vertical spacing between panels         |

## Loo plots (`loo`)
Style settings for PSIS-LOO model comparison plots.

| Key          | Type   | Default   | Description                                                                                      |
|--------------|--------|-----------|--------------------------------------------------------------------------------------------------|
| `output`     | dict   | —         | Output settings for the plot                                                                     |
| `box_color`  | string | `#005570` | Fill color of box plots. Used when only one value of k is present                               |
| `line_width` | float  | `0.5`     | Line width of the ELPD-LOO curves. Used when multiple values of k are present                   |
| `line_style` | string | `dashed`  | Line style of the ELPD-LOO curves. Used when multiple values of k are present                   |

### `loo.output`

| Key          | Type  | Default | Description                        |
|--------------|-------|---------|------------------------------------|
| `width`      | float | `10`    | Width of the figure in inches      |
| `height`     | float | `6`     | Height of the figure in inches     |

## Maps (`map`)
Style settings for the posterior map.

| Key        | Type | Default | Description                                         |
|------------|------|---------|-----------------------------------------------------|
| `geo`      | dict | —       | Geographic settings including projection and extent |
| `graphics` | dict | —       | Visual settings for objects, clusters and base map  |
| `legend`   | dict | —       | Settings for all legend elements                    |
| `output`   | dict | —       | Output dimensions                                   |

### `map.geo`
Controls the geographic projection, extent and base map data sources.

| Key              | Type   | Default | Description                                                                                      |
|------------------|--------|---------|--------------------------------------------------------------------------------------------------|
| `map_projection` | string | `null`  | CRS for rendering the map (PROJ string or EPSG code). Defaults to the data projection if not set |
| `extent`         | dict   | —       | Map extent in map CRS units. Defaults to the data extent if not set                              |
| `basemap`        | dict   | —       | Base map data sources                                                                            |

#### `map.geo.extent`
Controls the map extent. 

| Key     | Type  | Default | Description                                              |
|---------|-------|---------|----------------------------------------------------------|
| `x_min` | float | `null`  | Minimum x extent. `null` = auto-compute from data extent |
| `x_max` | float | `null`  | Maximum x extent. `null` = auto-compute from data extent |
| `y_min` | float | `null`  | Minimum y extent. `null` = auto-compute from data extent |
| `y_max` | float | `null`  | Maximum y extent. `null` = auto-compute from data extent |

#### `map.geo.basemap`
Controls which geographic data files are used for the base map.

| Key       | Type    | Default     | Description                                                                                |
|-----------|---------|-------------|--------------------------------------------------------------------------------------------|
| `add`     | boolean | `true`      | Whether to add a base map                                                                  |
| `polygon` | string  | `<DEFAULT>` | Path to a GeoJSON polygon file (land masses). `<DEFAULT>` = use bundled Natural Earth data |
| `line`    | string  | `<DEFAULT>` | Path to a GeoJSON line file (rivers, lakes). `<DEFAULT>` = use bundled Natural Earth data  |
| `point`   | string  | `null`      | Path to a GeoJSON point file (e.g. cities). `null` = no point layer                        |

### `map.graphics`
Controls the visual appearance of objects, clusters, confounders and the base map.

| Key           | Type | Default | Description                                |
|---------------|------|---------|--------------------------------------------|
| `objects`     | dict | —       | Style settings for all objects on the map  |
| `clusters`    | dict | —       | Style settings for cluster assignments     |
| `confounders` | dict | —       | Style settings for confounder alpha shapes |
| `basemap`     | dict | —       | Style settings for base map layers         |

#### `map.graphics.objects`
Controls the appearance of objects plotted on the map.

| Key         | Type    | Default   | Description                              |
|-------------|---------|-----------|------------------------------------------|
| `color`     | string  | `#000000` | Color of object markers                  |
| `marker`    | string  | `o`       | Matplotlib marker style                  |
| `size`      | float   | `5`       | Marker size in points squared            |
| `label`     | boolean | `true`    | Whether to add numeric labels to objects |
| `font_size` | int     | `5`       | Font size of object labels               |

#### `map.graphics.clusters`
Controls the appearance of cluster assignments on the map.

| Key                 | Type          | Default       | Description                                                                           |
|---------------------|---------------|---------------|---------------------------------------------------------------------------------------|
| `marker`            | string        | `o`           | Matplotlib marker style for cluster objects                                           |
| `color`             | string        | `max_cluster` | Object color: `max_cluster` = color by dominant cluster, `as_objects` = neutral color |
| `size`              | string\|float | `frequency`   | Marker size: `frequency` = scale by posterior probability, or fixed float e.g. `10`   |
| `max_size`          | float         | `50`          | Maximum marker size when `size` is `frequency`                                        |
| `line_width`        | string\|float | `frequency`   | Line width: `frequency` = scale by posterior probability, or fixed float e.g. `1.0`   |
| `max_line_width`    | float         | `1`           | Maximum line width when `line_width` is `frequency`                                   |
| `alpha`             | string\|float | `frequency`   | Opacity: `frequency` = scale by posterior probability, or fixed float e.g. `0.8`      |
| `pie_radius_factor` | float         | `0.008`       | Base pie radius as a fraction of the minimum map spa. For `dot` map only.             |

#### `map.graphics.confounders`
Controls the appearance of confounder alpha shapes on the map.

| Key      | Type         | Default | Description                                                    |
|----------|--------------|---------|----------------------------------------------------------------|
| `size`   | float        | `180`   | Marker size for confounder scatter points in points squared    |
| `color`  | list[string] | `[]`    | Colors for each confounder group. Empty = auto-generate colors |
| `buffer` | float        | `0.5`   | Buffer distance around alpha shapes in map CRS units           |
| `shape`  | float        | `20`    | Alpha shape concavity parameter. Larger = tighter shape        |

#### `map.graphics.basemap`
Controls the visual appearance of base map layers.

| Key                     | Type   | Default   | Description                             |
|-------------------------|--------|-----------|-----------------------------------------|
| `background`            | string | `#f0f8ff` | Background color of the map axes        |
| `polygon.color`         | string | `white`   | Fill color of land polygons             |
| `polygon.outline_color` | string | `grey`    | Outline color of (land) polygons        |
| `polygon.outline_width` | float  | `0.1`     | Outline width of (land) polygons        |
| `line.color`            | string | `skyblue` | Color of (river and lake) lines         |
| `line.width`            | float  | `0.5`     | Width of (river and lake) lines         |
| `point.color`           | string | `black`   | Color of point markers                  |
| `point.size`            | float  | `10`      | Size of point markers in points squared |
| `point.marker`          | string | `o`       | Matplotlib marker style for points      |

### `map.legend`
Controls which legend elements are shown and where.

| Key            | Type | Default | Description                                              |
|----------------|------|---------|----------------------------------------------------------|
| `clusters`     | dict | —       | Legend entry for cluster lines                           |
| `confounders`  | dict | —       | Legend entry for confounder alpha shapes                 |
| `lines`        | dict | —       | Legend entry for line width reference                    |
| `overview_map` | dict | —       | Inset overview map                                       |
| `index_table`  | dict | —       | Correspondence table mapping object numbers to names     |

#### `map.legend.clusters`
Legend for clusters.

| Key              | Type    | Default | Description                                             |
|------------------|---------|---------|---------------------------------------------------------|
| `add`            | boolean | `true`  | Whether to add the cluster legend                       |
| `log_likelihood` | boolean | `false` | Whether to show log likelihood values as cluster labels |
| `font_size`      | int     | `10`    | Font size of legend labels                              |
| `position.x`     | float   | `0.005` | Horizontal position in axes coordinates (0–1)           |
| `position.y`     | float   | `0.95`  | Vertical position in axes coordinates (0–1)             |

#### `map.legend.confounders`
Legend for confounders. 

| Key          | Type    | Default | Description                                   |
|--------------|---------|---------|-----------------------------------------------|
| `add`        | boolean | `true`  | Whether to add the confounder legend          |
| `font_size`  | int     | `10`    | Font size of legend labels                    |
| `position.x` | float   | `0.005` | Horizontal position in axes coordinates (0–1) |
| `position.y` | float   | `0.8`   | Vertical position in axes coordinates (0–1)   |

#### `map.legend.lines`
Only relevant for `line` maps. Controls the line width reference legend showing posterior frequency scale.

| Key                     | Type        | Default           | Description                                                  |
|-------------------------|-------------|-------------------|--------------------------------------------------------------|
| `add`                   | boolean     | `true`            | Whether to add the line width legend                         |
| `font_size`             | int         | `10`              | Font size of legend labels                                   |
| `position.x`            | float       | `0.005`           | Horizontal position in axes coordinates (0–1)                |
| `position.y`            | float       | `0.5`             | Vertical position in axes coordinates (0–1)                  |
| `reference_frequencies` | list[float] | `[0.5, 0.7, 0.9]` | Posterior frequencies shown as reference lines in the legend |

#### `map.legend.overview_map`
Controls the inset overview map showing broader geographic context.

| Key               | Type    | Default | Description                                                   |
|-------------------|---------|---------|---------------------------------------------------------------|
| `add`             | boolean | `false` | Whether to add the overview map                               |
| `extent_factor.x` | float   | `1.5`   | How much wider the overview is relative to the main map       |
| `extent_factor.y` | float   | `1.5`   | How much taller the overview is relative to the main map      |
| `width`           | float   | `0.3`   | Width of the overview window as a fraction of the main image  |
| `height`          | float   | `0.3`   | Height of the overview window as a fraction of the main image |
| `position.x`      | float   | `0.005` | Horizontal position in axes coordinates (0–1)                 |
| `position.y`      | float   | `0.15`  | Vertical position in axes coordinates (0–1)                   |

#### `map.legend.index_table`
Controls the index table mapping object numbers to names.

| Key            | Type    | Default | Description                                                                      |
|----------------|---------|---------|----------------------------------------------------------------------------------|
| `add`          | boolean | `true`  | Whether to add the index table                                                   |
| `show`         | string  | `all`   | Which objects to show: `all` or `in_cluster`                                     |
| `font_size`    | int     | `10`    | Font size of table entries                                                       |
| `n_columns`    | int     | `2`     | Number of columns in the table                                                   |
| `color_labels` | boolean | `true`  | Whether to color object names by their cluster color                             |
| `height`       | float   | `0.8`   | Height of the table as a fraction of the axes height                             |

### `map.output`

| Key      | Type  | Default | Description                        |
|----------|-------|---------|------------------------------------|
| `width`  | float | `14`    | Width of the map figure in inches  |
| `height` | float | `10`    | Height of the map figure in inches |
