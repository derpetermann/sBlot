"""
Script to generate minimal synthetic test data for sBlot tests.

Generates a small sBayes-compatible dataset with:
- 20 simulated objects
- 5 simulated features
- 1 simulated confounder
- 2 simulated areas
- 500 inferred posterior samples at K=1 and K=2

Simulation parameters are stored in config_simulate.yaml
Inference parameters are stored in config.yaml

Run from the project root:
    python tests/generate_test_data.py

Output is written to tests/data/. Commit the output to the repository
so tests can run without regenerating the data.
"""
import jax.random as random

from pathlib import Path
from sbayes.simulate.config import load_config
from sbayes.simulate.simulator import Simulator


def generate_test_data(
    simulate_config_path: Path,
    rng_seed: int = 0,
) -> None:
    """Generate minimal synthetic test data for sBlot tests.

    Args:
        simulate_config_path: Path to config_simulate.yaml.
        rng_seed: Random seed for reproducibility. Default is 0.
    """
    sim_config = load_config(simulate_config_path)
    sim = Simulator(sim_config)
    sim.prepare_simulation()
    sim.simulate(random.PRNGKey(rng_seed))
    sim.write_simulation(write_parameters = False)
    sim.infer()

if __name__ == "__main__":
    generate_test_data(
        simulate_config_path=Path(__file__).parent / "config_simulate.yaml",
    )