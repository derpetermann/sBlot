"""
Script to generate minimal synthetic test data for sBlot tests.

Generates a small sBayes-compatible dataset with:
- 20 objects
- 5 features
- 2 confounders
- 500 posterior samples at K=1 and K=2

Run from the project root:
    python tests/generate_test_data.py

Output is written to tests/data/.

Note: This script is intended to eventually be integrated into the sBayes
package as part of its test suite.
"""