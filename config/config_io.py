from __future__ import annotations

import os
import warnings

from core.utils import decompose_config_path, fix_relative_path
from pathlib import Path
from pandas import read_csv
from pydantic import BaseModel, DirectoryPath, Field, model_validator, PositiveInt
from pydantic_core import PydanticCustomError
from pydantic_core.core_schema import ValidationInfo
from pydantic.types import PathType
from ruamel.yaml import YAML
from sbayes.load_data import read_features_from_csv, Objects, Features, Confounder
from sbayes.results import Results
from typing import Annotated, Self, Iterator


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

    path_out: RelativeDirectoryPath = Field(
        default_factory=lambda: RelativePathType.fix_path("./results/plots")
    )
    """Path to the directory where plots will be saved."""

    burn_in: float = 0.2
    """Fraction of samples to discard as burn-in (0.0 to 1.0)."""

    thinning: PositiveInt = 1
    """Keep every nth sample to reduce memory usage (1 = keep all samples)."""

    @model_validator(mode="after")
    def validate_burn_in(self):
        if not 0.0 < self.burn_in < 1.0:
            raise ValueError(f"burn_in must be between 0 and 1, got {self.burn_in}.")
        return self


class WeightsLabelConfig(BaseConfig):
    """Style configuration for labels in weights plots."""
    add: bool = True
    names: list[str] = Field(default_factory=list)
    font_size: int = 6


class WeightsTitleConfig(BaseConfig):
    """Style configuration for title in weights plots."""
    add: bool = True
    font_size: int = 6


class WeightsLegendConfig(BaseConfig):
    """Style configuration for legend in weights plots."""
    corner_labels: WeightsLabelConfig = Field(default_factory=WeightsLabelConfig)
    title: WeightsTitleConfig = Field(default_factory=WeightsTitleConfig)


class WeightsOutputConfig(BaseConfig):
    """Style configuration for output of weights plots."""
    width_subplot: float = 2
    height_subplot: float = 2
    n_columns: int = 5


class WeightsConfig(BaseConfig):
    """Configuration for weights plots."""
    features: list[str] = Field(default_factory=list)
    legend: WeightsLegendConfig = Field(default_factory=WeightsLegendConfig)
    output: WeightsOutputConfig = Field(default_factory=WeightsOutputConfig)


class MapConfig(BaseConfig):
    """Configuration for map plots."""

    @model_validator(mode="after")
    def default_map_projection(self):
        if not self.map_projection:
            self.map_projection = self.data_projection
        return self


    @model_validator(mode="after")
    def disable_color_labels_for_density_map(self):
        if self.type == 'density_map':
            self.color_labels = False
        return self


class PlotsConfig(BaseConfig):
    """Which plots to generate and their analytical settings."""
    weights: WeightsConfig | None = None
    # preferences: PreferencesConfig | None = None
    # pies: PiesConfig | None = None
    # features: FeaturesConfig | None = None


class StyleConfig(FileConfig):
    """Root configuration loaded from config_style.yaml."""
    weights: WeightsConfig = Field(default_factory=WeightsConfig)


class PlotConfig(FileConfig):
    """Root configuration loaded from config_plot.yaml."""
    data: DataConfig
    results: ResultsConfig
    plots: PlotsConfig

    def read_data(self) -> tuple[Objects, Features, dict[str, Confounder]]:
        """Read objects, features and confounders from the data files defined in this config.

        Returns:
            Tuple of (objects, features, confounders).
        """
        confounder_names = find_confounder_names(
            self.data.features,
            self.data.feature_types,
        )
        return read_features_from_csv(
            data_path=self.data.features,
            feature_types_path=self.data.feature_types,
            confounder_names=confounder_names,
        )

    def read_results(self) -> Iterator[tuple[str, Results]]:
        """Iterate over all models in the results directory.

        Yields:
            Tuple of (model_name, Results) for each model found in path_in.
        """
        path_in = Path(self.results.path_in)
        cluster_files = sorted(path_in.glob("clusters_*.txt"))
        stats_files = sorted(path_in.glob("stats_*.txt"))

        for clusters_path, stats_path in zip(cluster_files, stats_files):
            _, _, model_name = clusters_path.stem.partition('_')
            results = Results.from_csv_files(
                clusters_path=clusters_path,
                parameters_path=stats_path,
                burn_in=self.results.burn_in,
            )
            yield model_name, results

class Config(FileConfig):
    """Root configuration."""
    plot_config: PlotConfig = Field(default_factory=PlotConfig)
    style_config: StyleConfig = Field(default_factory=StyleConfig)


def load_plot_config(
    config: str | Path,
    style_dir: str | Path | None = None,
) -> tuple[PlotConfig, StyleConfig]:
    """Load and merge all config files into a single PlotConfig object.

    Args:
        config: Path to config.yaml.
        style_dir: Optional path to directory containing user style config files.
                   Defaults to sblot/config/defaults/ if not provided.
    Returns:
        Tuple of (PlotConfig, StyleConfig).
    """
    import importlib.resources as pkg_resources
    from sblot import config as config_package

    plot_config = PlotConfig.from_config_file(config)

    if style_dir is None:
        ref = pkg_resources.files(config_package) / 'defaults' / 'config_style.yaml'
        with pkg_resources.as_file(ref) as style_path:
            style_config = StyleConfig.from_config_file(style_path)
    else:
        style_config = StyleConfig.from_config_file(style_dir)

    return plot_config, style_config


def set_defaults(config: dict, default_config: dict) -> dict:
    """Recursively fill missing fields in `config` with values from `default_config`.

    Fields already present in `config` are never overwritten. For nested
    dictionaries, the merge is applied recursively.

    Args:
        config: The user-provided config dictionary, modified in place.
        default_config: The default config dictionary to fall back on.
    Returns:
        The updated `config` dictionary.

    >>> set_defaults(config={0:0, 1:{1:0}, 2:{2:1}},
    ...              default_config={1:{1:1}, 2:{1:1, 2:2}})
    {0: 0, 1: {1: 0}, 2: {2: 1, 1: 1}}
    >>> set_defaults(config={0:0, 1:1, 2:2},
    ...              default_config={1:{1:1}, 2:{1:1, 2:2}})
    {0: 0, 1: 1, 2: 2}
    """
    for key in default_config:
        if key not in config:
            config[key] = default_config[key]
        elif isinstance(default_config[key], dict) and isinstance(config[key], dict):
            set_defaults(config[key], default_config[key])
    return config


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


