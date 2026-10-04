from pathlib import Path
import csv
import math
from bisect import bisect_right
from datetime import datetime

root = Path(__file__).resolve().parents[1]
left = root / "exports" / "ansys" / "python_wall_results.csv"
right = root / "exports" / "ansys" / "ansys_wall_results.csv"

def read_python(path):
    data = []
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        first_time = None
        for row in r:
            t = datetime.fromisoformat(row["timestamp"])
            if first_time is None:
                first_time = t
            elapsed = (t - first_time).total_seconds()
            data.append((elapsed, float(row["inner_surface_c"])))
    return data

def read_ansys(path):
    data = []
    with path.open(encoding="utf-8") as f:
        r = csv.reader(f, skipinitialspace=True)
        next(r)
        for row in r:
            if len(row) >= 2:
                try:
                    data.append((float(row[0]), float(row[1])))
                except ValueError:
                    pass
    return data

python_data = read_python(left)
ansys_data = read_ansys(right)

at = [t for t, _ in ansys_data]
av = [v for _, v in ansys_data]

def interpolate(t):
    i = bisect_right(at, t)
    if i == 0:
        return av[0]
    if i >= len(at):
        return av[-1]
    t0, v0 = at[i-1], av[i-1]
    t1, v1 = at[i], av[i]
    return v0 + (v1-v0) * (t-t0)/(t1-t0)

diffs = []

for t, py in python_data:

    t += 259200
    if at[0] <= t <= at[-1]:
        diffs.append(py - interpolate(t))

print(f"python_points={len(python_data)}")
print(f"ansys_points={len(ansys_data)}")
print(f"points_compared={len(diffs)}")
print(f"max_abs_difference_c={max(map(abs, diffs)):.6f}")
print(f"rms_difference_c={math.sqrt(sum(x*x for x in diffs)/len(diffs)):.6f}")

