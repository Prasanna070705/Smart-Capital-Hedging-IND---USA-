# src/run_all.py
# Week 1 pipeline: rebuilds every output from the raw data in one command, in the right order.
# Run from anywhere:  python src/run_all.py            (uses the saved raw snapshot)
#                     python src/run_all.py --fetch    (re-downloads all FRED data first - changes results!)
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (label, command) in dependency order: each step only reads what earlier steps wrote
STEPS = [
    ("Features",            ["src/features.py"]),
    ("Validate features",   ["src/validate_features.py"]),
    ("Obj 1: Monte Carlo",  ["src/risk_baseline.py"]),
    ("Obj 1: validation",   ["src/validate_risk.py"]),
    ("Obj 2: forward",      ["src/forward_pricing.py"]),
    ("Obj 2: static hedge", ["src/static_hedge.py"]),
    ("Unit + smoke tests",  ["-m", "unittest", "discover", "tests"]),
]


def run(label, args):
    """Run one step with the same Python as this script; stop the pipeline if it fails."""
    start = time.time()
    result = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    seconds = time.time() - start
    if result.returncode != 0:
        print(f"  FAIL  {label:22s} ({seconds:.1f}s)\n")
        print(result.stdout[-3000:])
        print(result.stderr[-3000:])
        sys.exit(f"Pipeline stopped at: {label}")
    print(f"  ok    {label:22s} ({seconds:.1f}s)")
    return result.stdout


def main():
    steps = list(STEPS)
    if "--fetch" in sys.argv:
        steps.insert(0, ("Ingestion (FRED)", ["src/ingestion.py"]))
        print("WARNING: --fetch re-downloads FRED data, so results will differ from the committed snapshot.\n")

    print("Week 1 pipeline")
    total = time.time()
    outputs = {label: run(label, args) for label, args in steps}
    print(f"\nAll {len(steps)} steps passed in {time.time() - total:.1f}s.\n")

    # The combined Objective 1 + 2 table, straight from static_hedge.py's own output
    table = outputs["Obj 2: static hedge"]
    print(table[: table.index("Saved")].rstrip())


if __name__ == "__main__":
    main()