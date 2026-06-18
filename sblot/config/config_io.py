from __future__ import annotations

import os
import re
import warnings

from pathlib import Path
from pandas import read_csv
from pydantic import BaseModel, DirectoryPath, Field, model_validator, PositiveInt, field_validator
from pydantic_core import PydanticCustomError
from pydantic_core.core_schema import ValidationInfo
from pydantic.types import PathType
from ruamel.yaml import YAML
from sbayes.load_data import read_features_from_csv, Data
from sbayes.results import Results
from sblot.core.utils import fix_relative_path
from typing import Annotated, Self, Iterator, Literal, NamedTuple, Union, get_args

MapType = Literal["pie", "line", "idw"]


class ModelResults(NamedTuple):
    name: str | None
    results: Results

class RelativePathType(PathType):
    """Path validator that resolves paths relative to a base directory.

    Set BASE_DIR before loading any config file:
        RelativePathType.BASE_DIR = Path('path/to/config/dir')
    """

    BASE_DIR: DirectoryPath = Path(".")

    @classmethod
    def fix_path(cls, value: Path | str) -> Path:
        """Resolve a path relative to BASE_DIR."""
        return fix_relative_path(value, cls.BASE_DIR)

    @staticmethod
    def validate_file(path: Path, _: ValidationInfo) -> Path:
        """Resolve and validate that path points to an existing file."""
        path = RelativePathType.fix_path(path)
        if path.is_file():
            return path
        raise PydanticCustomError(
            'path_not_file',
            'Path does not point to a file: {path}',
            {'path': str(path)}
        )

    @staticmethod
    def validate_directory(path: Path, _: ValidationInfo) -> Path:
        """Resolve the path and create directory if it does not exist."""
        path = RelativePathType.fix_path(path)
        os.makedirs(path, exist_ok=True)
        if path.is_dir():
            return path
        raise PydanticCustomError(
            'path_not_directory',
            'Path does not point to a directory: {path}',
            {'path': str(path)}
        )


RelativeFilePath = Annotated[Path, RelativePathType('file')]
"""A path that must point to an existing file, resolved relative to the config file location."""

RelativeDirectoryPath = Annotated[Path, RelativePathType('dir')]
"""A path to a directory, resolved relative to the config file location. Created if absent."""


class BaseConfig(BaseModel, extra='forbid'):
    """Base class for all config classes — shared validation only."""

    def __getitem__(self, key: str):
        return self.__getattribute__(key)

    @classmethod
    def deprecated_attributes(cls) -> list[str]:
        return []

    @model_validator(mode="before")
    @classmethod
    def warn_about_deprecated_attributes(cls, values: dict) -> dict:
        for key in cls.deprecated_attributes():
            if key in values:
                warnings.warn(
                    f"The '{key}' key in {cls.__name__} is deprecated "
                    f"and will be removed in a future version of sblot.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                values.pop(key)
        return values


class FileConfig(BaseConfig):
    """Base class for top-level config classes that are loaded from a file."""

    @classmethod
    def from_config_file(cls, path: str | Path) -> Self:
        """Load and validate a config file.

        Args:
            path: Path to the config file.
        Returns:
            Validated config instance of the calling class.
        """
        path = Path(path).absolute()
        RelativePathType.BASE_DIR = path.parent

        yaml = YAML(typ='safe')
        with open(path) as f:
            config_dict = yaml.load(f)

        return cls(**config_dict)  # type: ignore[arg-type]


class DataConfig(BaseConfig):
    """Base class for data config classes."""

    features: RelativeFilePath
    """Path to the features CSV file (columns: id, x, y, confounder 1, ..., feature1, ...)."""

    feature_types: RelativeFilePath
    """Path to the feature_types.yaml file (defines the feature type for each feature)."""

    projection: str = "epsg:4326"
    """CRS of the input data as a PROJ string or EPSG code."""


class ResultsConfig(BaseConfig):
    """Base class for results config classes."""

    path_in: RelativeDirectoryPath
    """Path to the sBayes results files (clusters and stats)."""

    path_out: RelativeDirectoryPath | None = None
    """Path to the directory where plots will be saved.
    Defaults to path_in + '_plots' if not provided."""

    burn_in: float = 0.2
    """Fraction of samples to discard as burn-in (0.0 to 1.0)."""

    thinning: PositiveInt = 1
    """Keep every nth sample to reduce memory usage (1 = keep all samples)."""

    @model_validator(mode="after")
    def set_default_path_out(self):
        if self.path_out is None:
            self.path_out = RelativePathType.fix_path(f"{self.path_in}_plots")
        else:
            self.path_out = RelativePathType.fix_path(self.path_out)
        return self

    @model_validator(mode="after")
    def validate_burn_in(self):
        if not 0.0 < self.burn_in < 1.0:
            raise ValueError(f"burn_in must be between 0 and 1, got {self.burn_in}.")
        return self


class GlobalConfig(BaseConfig):
    """Global settings applied to all plots."""
    format: str = "pdf"
    """Output file format (pdf, png, svg)."""
    resolution: int = 300
    """Output resolution in DPI."""
    cluster_colors: list[str] = Field(default_factory=list)
    """Cluster colors used by map, pie charts and other plots."""
    n_clusters: int = 0
    """Number of clusters — set at load time from results."""


class WeightsLabelConfig(BaseConfig):
    """Style configuration for labels in weights plots."""
    add: bool = True
    names: list[str] = Field(default_factory=list)
    """Corner labels for the simplex. If empty, inferred from component names."""
    font_size: int = 6

    def resolve_names(self, results: Results) -> list[str]:
        """Return corner labels, inferring from results if not explicitly set.

        Args:
            results: MCMC results defining the component ordering.
        Returns:
            Ordered list of corner labels, e.g. ['A', 'F', 'U'].
        """
        if self.names:
            return self.names

        # Infer from component names — cluster is always 'C'
        labels = ["C"] + [c[0].upper() for c in results.confounders]

        if len(set(labels)) < len(labels):
            warnings.warn(
                "Two or more inferred component labels are identical. "
                "Consider providing explicit names in config_style.yaml."
            )
        return labels


class PositionConfig(BaseConfig):
    x: float = 0.0
    y: float = 1.0


class WeightsMeanConfig(BaseConfig):
    """Style for the mean weight marker."""
    show: bool = True
    color: str = "#ed1696"
    size: int = 50
    marker: str = "o"


class WeightsSimplexConfig(BaseConfig):
    """Style for the simplex plot."""
    color: str = "#005570"
    border_width: float = 1.0
    padding: float = 0.1
    label_stretch: float = 1.15


class WeightsOutputConfig(BaseConfig):
    """Output settings for weights plots."""
    width_subplot: float = 2
    height_subplot: float = 2
    n_columns: int = 5
    spacing_horizontal: float = 0.1
    spacing_vertical: float = 0.1


class WeightsTitleConfig(BaseConfig):
    add: bool = True
    font_size: int = 6
    position: PositionConfig = Field(default_factory=PositionConfig)


class WeightsLegendConfig(BaseConfig):
    """Style configuration for legend in weights plots."""
    corner_labels: WeightsLabelConfig = Field(default_factory=WeightsLabelConfig)
    title: WeightsTitleConfig = Field(default_factory=WeightsTitleConfig)


class WeightsConfig(BaseConfig):
    """Configuration for weights plots."""
    # Analytical
    features: list[str] = Field(default_factory=list)

    # Style
    legend: WeightsLegendConfig = Field(default_factory=WeightsLegendConfig)
    output: WeightsOutputConfig = Field(default_factory=WeightsOutputConfig)
    simplex: WeightsSimplexConfig = Field(default_factory=WeightsSimplexConfig)
    mean: WeightsMeanConfig = Field(default_factory=WeightsMeanConfig)

# Pies plot
class PiesPieConfig(BaseConfig):
    """Style configuration for individual pie charts."""
    radius: float = 15
    no_cluster_color: str = "lightgrey"


class PiesAxesConfig(BaseConfig):
    """Axes limits and label positions for pie charts."""
    x_min: float = 0
    x_max: float = 160
    y_min: float = -10
    y_max: float = 10
    index_x: float = 0.20
    name_x: float = 0.25
    label_y: float = 0.5


class PiesLabelConfig(BaseConfig):
    """Label settings for pie charts."""
    index_size: int = 15
    name_size: int = 15
    max_label_length: int = 10


class PiesOutputConfig(BaseConfig):
    """Output settings for pie charts."""
    width: float = 4
    height: float = 2
    n_columns: int = 10
    spacing_horizontal: float = 0.01
    spacing_vertical: float = 0.01


class PiesConfig(BaseConfig):
    """Configuration for pies plots."""
    # Analytical
    enabled: bool = True
    """Pie charts are generated when this section is present."""

    # Style
    label: PiesLabelConfig = Field(default_factory=PiesLabelConfig)
    pie: PiesPieConfig = Field(default_factory=PiesPieConfig)
    axes: PiesAxesConfig = Field(default_factory=PiesAxesConfig)
    output: PiesOutputConfig = Field(default_factory=PiesOutputConfig)

# Preference plots
class PreferencesComponentConfig(BaseConfig):
    component: str
    """Component name — confounder (e.g. 'family') or "cluster"."""
    groups: list[str] = Field(default_factory=list)
    """Group names to plot. Empty = plot all groups within the component."""


class PreferencesLabelConfig(BaseConfig):
    """Label settings for preference plots."""
    add: bool = True
    font_size: int = 4


class PreferencesOutputConfig(BaseConfig):
    """Output settings for preference plots."""
    width_subplot: float = 3
    height_subplot: float = 3
    n_columns: int = 5
    spacing_horizontal: float = 0.2
    spacing_vertical: float = 0.3


class PreferencesTitleConfig(BaseConfig):
    """Title settings for preference plots."""
    add: bool = True
    font_size: int = 6
    position: PositionConfig = Field(default_factory=PositionConfig)


class PreferencesLegendConfig(BaseConfig):
    """Legend settings for preference plots."""
    labels: PreferencesLabelConfig = Field(default_factory=PreferencesLabelConfig)
    title: PreferencesTitleConfig = Field(default_factory=PreferencesTitleConfig)


class PreferencesConfig(BaseConfig):
    # Analytical
    """Settings for preference plots."""
    features: list[str] = Field(default_factory=list)
    """Features to plot. Empty = plot all features."""
    components: list[PreferencesComponentConfig] = Field(default_factory=list)
    """Components to plot. Empty = plot all components."""
    reference: str | None = None
    """Optional reference component shown as overlay behind each preference plot."""

    # Style
    legend: PreferencesLegendConfig = Field(default_factory=PreferencesLegendConfig)
    output: PreferencesOutputConfig = Field(default_factory=PreferencesOutputConfig)
    color: str = "#005570"
    reference_color: str = "#b0b0b0"


class LOOOutputConfig(BaseConfig):
    width: float = 10
    """Width of the figure in inches """
    height: float = 6
    """Height of the figure in inches """

# LOO
class LOOConfig(BaseConfig):
    """Settings for LOO plots."""
    # Analytical
    enabled: bool = False
    """Loo plots are generated when this section is present."""

    # Style
    output: LOOOutputConfig = Field(default_factory=LOOOutputConfig)
    """Output settings for the plot """
    box_color: str = "#005570"
    """Fill color of box plots. Used when only one value of k is present"""
    line_width: float = 0.5
    """Line width of the ELPD-LOO curves. Used when multiple values of k are present """
    line_style: Literal["dashed", "dotted", "solid"] = "dashed"
    """Line style of the ELPD-LOO curves. Used when multiple values of k are present. 
    Either "dashed", "dotted" or "solid"."""


# Map
class MapExtentConfig(BaseConfig):
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    """Spatial extent in map CRS units. None = auto-compute from data."""

class MapBaseMapConfig(BaseConfig):
    """Configuration for base map layers."""
    add: bool = True
    polygon: str = "<DEFAULT>"
    """Path to GeoJSON polygon file (country borders, land masses).
    Use '<DEFAULT>' for the package default or provide a custom path."""
    line: str = "<DEFAULT>"
    """Path to GeoJSON line file (rivers, coastlines).
    Use '<DEFAULT>' for the package default or provide a custom path."""
    point: str | None = None
    """Optional path to GeoJSON point file (cities, landmarks).
    None = no point layer."""


class MapBaseMapPolygonConfig(BaseConfig):
    color: str = "white"
    """Color for base map polygons."""
    outline_color: str | None =  "black"
    """Outline color for base map polygons."""
    outline_width: float = 1
    """Outline width for base map polygons."""


class MapBaseMapLineConfig(BaseConfig):
    color: str = "skyblue"
    """Color for base map lines."""
    width: float = 1
    """Width for base map lines."""


class MapBaseMapPointConfig(BaseConfig):
    color: str = "black"
    """Color for base map points."""
    size: float = 10
    """Size for base map points."""
    marker: str = "o"
    """Marker for base map points."""


class MapGraphicBaseMapConfig(BaseConfig):
    """Visual style for base map layers."""
    polygon: MapBaseMapPolygonConfig = Field(default_factory=MapBaseMapPolygonConfig)
    line: MapBaseMapLineConfig = Field(default_factory=MapBaseMapLineConfig)
    point: MapBaseMapPointConfig = Field(default_factory=MapBaseMapPointConfig)
    background: str = "white"


class MapGraphicClusterConfig(BaseConfig):
    """Visual style for clusters on the map."""
    marker: str = "o"
    """Marker shape for objects in clusters."""
    color: Literal["max_cluster", "as_objects"] = "max_cluster"
    """Color of each site marker.
    'max_cluster' = colored by the cluster with the highest posterior assignment probability.
    'as_objects' = neutral color, same as non-cluster sites."""
    size: str | float = "frequency"
    """Point size. 'frequency' = scale by posterior frequency, or fixed float."""
    max_size: float = 50.0
    """Maximum point size when size is 'frequency'."""
    line_width: str | float = "frequency"
    """Line width. 'frequency' = scale by posterior frequency, or fixed float."""
    max_line_width: float = 3.0
    """Maximum line width when line_width is 'frequency'."""
    alpha: str | float = "frequency"
    """Opacity. 'frequency' = scale by posterior frequency, or fixed float."""
    pie_radius_factor: float = 0.008
    """Base pie radius as a fraction of the minimum map span (pie map only)."""


class MapGraphicObjectsConfig(BaseConfig):
    """Visual style for objects, e.g. languages."""
    color: str = "black"
    """Color for map objects."""
    size: float = 5
    """Size for map objects."""
    marker: str = "o"
    """Marker for map objects."""
    label: bool = True
    """Add label for map objects?"""
    font_size: int = 6
    """Font size for map object labels."""


class MapGraphicsConfounderConfig(BaseConfig):
    """Visual style for confounder overlays."""
    size: float = 180
    """Size of alpha shape objects."""
    color: list[str] = Field(default_factory=list)
    """Family colors. Empty = auto-generated."""
    buffer: float = 0.5
    """distance in map CRS units to expand the alpha shape outward before drawing. 
    Creates a smooth, slightly inflated polygon. Larger values = more padding around the boundary."""
    shape: float = 20
    """The alpha parameter controlling concavity of the alpha shape. 
    Larger values produce tighter, more concave shapes that follow the point distribution more closely."""


class MapGraphicsConfig(BaseConfig):
    """Configuration for map graphics."""
    basemap: MapGraphicBaseMapConfig = Field(default_factory=MapGraphicBaseMapConfig)
    objects: MapGraphicObjectsConfig = Field(default_factory=MapGraphicObjectsConfig)
    clusters: MapGraphicClusterConfig = Field(default_factory=MapGraphicClusterConfig)
    confounders: MapGraphicsConfounderConfig = Field(default_factory=MapGraphicsConfounderConfig)


class MapOutputConfig(BaseConfig):
    """Configuration for map output."""
    width: float = 14
    """Width for map output."""
    height: float = 10
    """Height for map output."""


class MapLegendClustersPositionConfig(BaseConfig):
    """Position for map legend clusters."""
    x: float = 1.0
    """Horizontal position for map legend clusters."""
    y: float = 1.0
    """Vertical position for map legend clusters."""


class MapLegendClustersConfig(BaseConfig):
    """Visual style for cluster legend."""
    add: bool = True
    """Add clusters to legend."""
    log_likelihood: bool = False
    """Show log likelihood for cluster legend."""
    font_size: int = 6
    """Font size for clusters in legend."""
    position: PositionConfig = Field(default_factory=PositionConfig)
    """Position for cluster legend."""


class MapLegendConfoundersConfig(BaseConfig):
    """Visual style for confounder legend."""
    add: bool = True
    """Add confounders to legend."""
    font_size: int = 6
    """Font size for confounders in legend."""
    position: PositionConfig = Field(default_factory=PositionConfig)
    """Position for confounder legend."""


class MapLegendLinesConfig(BaseConfig):
    """Visual style for line legend."""
    add: bool = True
    """Add lines to legend."""
    font_size: int = 6
    """Font size for lines in legend."""
    position: PositionConfig = Field(default_factory=PositionConfig)
    """Position for lines in legend."""
    reference_frequencies: list[float] = [0.5, 0.7, 0.9]
    """Reference frequencies for lines in legend."""


class MapLegendOverviewExtentFactorConfig(BaseConfig):
    """Scaling factors for the overview map extent."""
    x: float = 2.0
    """How much wider the overview is relative to the main map."""
    y: float = 2.0
    """How much taller the overview is relative to the main map."""


class MapLegendOverviewConfig(BaseConfig):
    """Visual style for the overview map."""
    add: bool = True
    """Add overview map to legend."""
    extent_factor: MapLegendOverviewExtentFactorConfig = Field(default_factory=MapLegendOverviewExtentFactorConfig)
    """Scaling factors for the overview map."""
    width: float = 0.1
    """Width for overview map in fractions of image width."""
    height: float = 0.1
    """Height for overview map in fractions of image height."""
    position: PositionConfig = Field(default_factory=PositionConfig)
    """Position for overview map."""


class MapLegendIndexTableConfig(BaseConfig):
    """Visual style for the language index table."""
    add: bool = True
    """Whether to add the index table to the map."""
    show: Literal["all", "in_cluster"] = "all"
    """Which languages to show in the index table. 'all' = all languages,
    'in_cluster' = only languages assigned to a cluster."""
    font_size: int = 6
    """Font size for the index table."""
    n_columns: int = 5
    """Number of columns in the index table."""
    color_labels: bool = True
    """Whether to color language names by their cluster color."""
    height: float = 0.2
    """Height of the index table in fractions of image height."""


class MapLegendConfig(BaseConfig):
    """Configuration for map legend."""
    clusters: MapLegendClustersConfig = Field(default_factory=MapLegendClustersConfig)
    confounders: MapLegendConfoundersConfig = Field(default_factory=MapLegendConfoundersConfig)
    lines: MapLegendLinesConfig = Field(default_factory=MapLegendLinesConfig)
    overview_map: MapLegendOverviewConfig = Field(default_factory=MapLegendOverviewConfig)
    index_table: MapLegendIndexTableConfig = Field(default_factory=MapLegendIndexTableConfig)


class MapGeoConfig(BaseConfig):
    map_projection: str | None = None
    """CRS for rendering the map as a PROJ string or EPSG code.
    If None, defaults to the data projection from config.yaml."""
    extent: MapExtentConfig = Field(default_factory=MapExtentConfig)
    basemap: MapBaseMapConfig = Field(default_factory=MapBaseMapConfig)
    """Config for base map layers."""


    def resolve_projection(self, data_projection: str) -> str:
        """Return map projection, falling back to data projection if not set."""
        return self.map_projection or data_projection


class MapLineConfig(BaseConfig):
    """Visual settings for cluster connection lines."""
    graph: Literal["complete", "delaunay", "gabriel"] = "gabriel"
    """Graph type used to connect sites within a cluster.
    'gabriel' = Gabriel graph (sparse, no crossing edges),
    'delaunay' = Delaunay triangulation (denser),
    'complete' = all pairwise connections (densest)."""



class MapIdwConfig(BaseConfig):
    """Parameters for IDW interpolation map."""
    resolution: int = 50000
    """Grid cell size in map CRS units. Smaller = finer grid, slower computation."""
    power: int = 2
    """Distance decay power. Higher = more influence from nearby points."""
    background_weight: float = 1.0
    """Weight of background color in areas far from any data point."""


class MapConfig(BaseConfig):
    type: Union[Literal["all"], list[MapType], MapType] = "line"
    """Map type. Either 'pie', 'line' or 'idw'"""
    plot_confounder: str | None = None
    """Add a confounder to the map."""
    labels: str = "all"
    """Add labels to the map. Either "all", "in_cluster" or none"""
    min_posterior_probability: float | None =  None
    """Minimum posterior probability for objects in a cluster to appear in the map. None = include all objects. 
    Set to a value between 0 and 1 e.g. 0.9 = only show objects assigned to the cluster in at least 90% of posterior samples."""
    per_cluster: bool = False
    """If True, generate a separate map for each cluster showing only that cluster's
    assignments. If False, generate a single map showing all clusters together."""
    line: MapLineConfig = Field(default_factory=MapLineConfig)
    """Configuration for line map."""
    idw: MapIdwConfig = Field(default_factory=MapIdwConfig)
    """Configuration for idw map."""

    # Style
    geo: MapGeoConfig = Field(default_factory=MapGeoConfig)
    """Map projection, base map and map extent."""
    graphics: MapGraphicsConfig = Field(default_factory=MapGraphicsConfig)
    """Config for map graphics."""
    legend: MapLegendConfig = Field(default_factory=MapLegendConfig)
    """Config for map legend."""
    output: MapOutputConfig = Field(default_factory=MapOutputConfig)
    """Config for map output."""

    @field_validator("type", mode="before")
    @classmethod
    def expand_all(cls, value):
        if value == "all":
            return list(get_args(MapType))
        return value

    @model_validator(mode="after")
    def validate_min_posterior_probability(self):
        if self.min_posterior_probability is not None:
            if not 0.0 < self.min_posterior_probability < 1.0:
                raise ValueError(
                    f"min_posterior_probability must be between 0 and 1, "
                    f"got {self.min_posterior_probability}."
                )
        return self


class PlotsConfig(BaseConfig):
    """Which plots to generate and their analytical settings."""
    weights: WeightsConfig | None = None
    pies: PiesConfig | None = None
    preferences: PreferencesConfig | None = None
    map: MapConfig | None = None
    loo: LOOConfig | None = None


class StyleConfig(FileConfig):
    global_: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    pies: PiesConfig = Field(default_factory=PiesConfig)
    preferences: PreferencesConfig = Field(default_factory=PreferencesConfig)
    map: MapConfig = Field(default_factory=MapConfig)
    loo: LOOConfig = Field(default_factory=LOOConfig)


class ExperimentConfig(FileConfig):
    """Root configuration loaded from config_plot.yaml."""
    data: DataConfig
    results: ResultsConfig
    plots: PlotsConfig


class Config(BaseConfig):
    """Root configuration for a sblot plotting run."""
    experiment: ExperimentConfig
    style: StyleConfig


    def read_data(self) -> Data:
        """Read objects, features and confounders from the data files defined in this config.

        Returns:
            Tuple of (objects, features, confounders).
        """
        confounder_names = find_confounder_names(
            self.experiment.data.features,
            self.experiment.data.feature_types,
        )
        return read_features_from_csv(
            data_path=self.experiment.data.features,
            feature_types_path=self.experiment.data.feature_types,
            confounder_names=confounder_names,
        )


    def read_results(self) -> Iterator[ModelResults]:
        """Iterate over all models in the results directory.

        Handles two folder structures:
        - Flat: path_in contains samples files directly (single model)
        - Nested: path_in contains subfolders, each with samples files

        Yields:
            ModelResults(name, results) for each model found.
        """
        path_in = Path(self.experiment.results.path_in)

        # Check if results files are directly in path_in or in subfolders
        direct_files = sorted(path_in.glob("samples_*.h5"))
        if direct_files:
            # Flat structure — single model in path_in
            model_dirs = [path_in]
            experiment_name = path_in.parent.name
        else:
            # Nested structure — one subfolder per model
            matched_dirs = [
                (d, re.search(r'K(\d+)', d.name))
                for d in path_in.iterdir() if d.is_dir()
            ]
            model_dirs = sorted(
                [d for d, m in matched_dirs if m is not None],
                key=lambda d: int(re.search(r'K(\d+)', d.name).group(1))
            )
            experiment_name = path_in.name

        if not model_dirs:
            raise FileNotFoundError(f"No results found in {path_in}.")

        burn_in = self.experiment.results.burn_in
        thinning = self.experiment.results.thinning

        for model_dir in model_dirs:
            samples_paths = sorted(model_dir.glob("samples_*.h5"))
            if not samples_paths:
                continue

            runs = [
                Results.from_h5(p, burn_in=burn_in, subsample_interval=thinning)
                for p in samples_paths
            ]
            yield ModelResults(
                name=experiment_name,
                results=Results.concatenate(runs),
            )


def load_config(
    config: str | Path,
    style_dir: str | Path | None = None,
) -> Config:
    """Load and merge all config files into a single Config object.

    Args:
        config: Path to config_plot.yaml.
        style_dir: Optional path to config_style.yaml. If not provided,
                   all style settings default to package defaults defined
                   in the StyleConfig class.
    Returns:
        Config object containing both ExperimentConfig and StyleConfig.
    """
    experiment = ExperimentConfig.from_config_file(config)

    if style_dir is None:
        style = StyleConfig()
    else:
        style = StyleConfig.from_config_file(style_dir)

    return Config(experiment=experiment, style=style)


def find_confounder_names(
    data_path: Path | str,
    feature_types_path: Path | str,
) -> list[str]:
    """Extract confounder names from the features CSV file.

    Confounder columns are those that are not features (defined in feature_types)
    and not metadata columns (id, x, y).

    Args:
        data_path: Path to the features CSV file.
        feature_types_path: Path to the feature types YAML file.
    Returns:
        List of confounder column names.
    """
    data_path = Path(data_path).absolute()
    feature_types_path = Path(feature_types_path).absolute()

    data = read_csv(data_path)

    yaml = YAML(typ='safe')
    with open(feature_types_path) as f:
        feature_types = yaml.load(f)

    metadata = {"id", "x", "y", "name"}
    feature_names = set(feature_types.keys())
    all_columns = set(data.columns.tolist())

    return list(all_columns - feature_names - metadata)


