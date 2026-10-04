from pathlib import Path
import csv
import math
import sys

root = Path(__file__).resolve().parents[1]
left = root / "exports" / "ansys" / "python_wall_results.csv"
right = root / "exports" / "ansys" / "ansys_wall_results.csv"
if not left.exists() or not right.exists():
    print("ANSYS comparison is waiting for both python_wall_results.csv and ansys_wall_results.csv")
    raise SystemExit(0)

def read(path):
    with path.open(encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        return [float(x["inner_surface_c"]) for x in r]
a, b = read(left), read(right)
if len(a) != len(b): raise SystemExit("Different result lengths")
d = [x-y for x,y in zip(a,b)]
print(f"max_abs_difference_c={max(map(abs,d)):.6f}")
print(f"rms_difference_c={math.sqrt(sum(x*x for x in d)/len(d)):.6f}")
