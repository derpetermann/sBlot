import argparse
import importlib.resources as resources
import shutil

from pathlib import Path
from sblot.config.config_io import load_config, read_data, read_results
from sblot.plots.preferences import plot_preferences
from sblot.plots.weights import plot_weights
from sblot.plots.pies import plot_pies
from sblot.plots.map import plot_maps
from sblot.plots.loo import plot_loo

PLOT_TYPES = ["weights", "preferences", "pies", "map", "loo"]


def main(
    config: str | Path,
    style: str | Path | None = None,
    plot_types: list[str] | None = None,
) -> None:
    """Run the sBlot plotting pipeline.

    Loads configuration, reads data and results, and generates all plots
    specified in the config file.

    Args:
        config: Path to config_plot.yaml.
        style: Optional path to config_style.yaml. Defaults to package
               defaults if not provided.
        plot_types: Optional list of plot types to generate. If None, all
                    plots enabled in the config are generated.
    """

    config = load_config(config, style)
    data = read_data(config)

    def enabled(name: str) -> bool:
        return (plot_types is None or name in plot_types) and bool(getattr(config.experiment.plots, name))
    all_models = list(read_results(config))

    for model in all_models:
        if enabled("weights"):
            plot_weights(model.results, config)
        if enabled("preferences"):
            plot_preferences(model.results, config)
        if enabled("pies"):
            plot_pies(model.results, data, config)
        if enabled("map"):
            plot_maps(model.results, data, config)

    if enabled("loo"):
        plot_loo(all_models, config)


def init(target_dir: str | Path) -> None:
    """Copy example config files to a target directory.

    Copies config_plot.yaml and config_style.yaml from the package
    examples to the target directory, so users can customise them.

    Args:
        target_dir: Directory to copy example configs to.
    """


    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in ['config_plot.yaml', 'config_style.yaml']:
        ref = resources.files('sblot.data.example_configs') / filename
        with resources.as_file(ref) as src:
            dst = target_dir / filename
            if dst.exists():
                print(f"Skipping {filename} — already exists in {target_dir}.")
            else:
                shutil.copy(src, dst)
                print(f"Copied {filename} to {target_dir}.")


def cli() -> None:
    """Command line entry point for the sBlot pipeline.

    Usage:
        sblot -c config_plot.yaml [-s config_style.yaml]
        sblot --init my_experiment/

    Examples:
        sblot -c config_plot.yaml
        sblot -c config_plot.yaml -s config_style.yaml
        sblot --init my_experiment/
    """


    parser = argparse.ArgumentParser(
        description="Generate plots to visualise the results of an sBayes analysis.",
        prog="sblot",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        help="Path to config_plot.yaml.",
    )
    parser.add_argument(
        "-s", "--style",
        type=Path,
        nargs="?",
        default=None,
        help="Optional path to config_style.yaml. "
             "Defaults to package defaults if not provided.",
    )
    parser.add_argument(
        "-p", "--plots",
        dest="plot_types",
        nargs="+",
        choices=PLOT_TYPES,
        default=None,
        metavar="PLOT_TYPE",
        help=f"Plot type(s) to generate. Choose from: {', '.join(PLOT_TYPES)}. "
             "Defaults to all types enabled in the config.",
    )
    parser.add_argument(
        "--init",
        type=Path,
        nargs="?",
        const=Path(".."),
        default=None,
        metavar="TARGET_DIR",
        help="Copy example config files to TARGET_DIR. "
             "Defaults to current directory if no path is provided.",
    )
    cli_args = parser.parse_args()

    if cli_args.init is not None:
        init(cli_args.init)
    elif cli_args.config is not None:
        main(config=cli_args.config, style=cli_args.style, plot_types=cli_args.plot_types)
    else:
        parser.print_help()


if __name__ == '__main__':
    cli()