import subprocess
import sys
import time
from pathlib import Path

# project root
BASE_DIR = Path(__file__).parent
SCRIPTS_DIR = BASE_DIR / "scripts"

# the three steps in order
STEPS = [
    ("FHFA acquisition", "download_fhfa.py"),
    ("Census acquisition", "download_census.py"),
    ("EDA + integration + visualizations", "eda_integrate.py"),
]


# run one script with the same python that ran run_all
def run_step(label, script_name):
    script_path = SCRIPTS_DIR / script_name
    print(f"\n{'=' * 70}")
    print(f"  STEP: {label}")
    print(f"  Script: scripts/{script_name}")
    print(f"{'=' * 70}\n")

    start = time.time()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=BASE_DIR,
    )
    elapsed = time.time() - start

    # stop the chain on any failure
    if result.returncode != 0:
        print(f"\n[FAILED] {label} exited with code {result.returncode}")
        sys.exit(result.returncode)

    print(f"\n[OK] {label} completed in {elapsed:.1f}s")


# run all three. stop on first failure
def main():
    print("Running full IS477-SP26 workflow")
    print(f"Project root: {BASE_DIR}")
    print(f"Python: {sys.executable}")

    total_start = time.time()
    for label, script in STEPS:
        run_step(label, script)
    total_elapsed = time.time() - total_start

    print(f"\n{'=' * 70}")
    print(f"  ALL STEPS COMPLETE in {total_elapsed:.1f}s")
    print(f"{'=' * 70}")
    print("Outputs:")
    print("  data/raw/fhfa/          FHFA HPI files + SHA-256 manifest")
    print("  data/raw/census/        Census ACS files + SHA-256 manifest")
    print("  data/integrated/        hpi_census_merged.csv")
    print("  results/visualizations/ 5 PNG charts")


if __name__ == "__main__":
    main()
