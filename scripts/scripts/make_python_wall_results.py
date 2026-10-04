from pathlib import Path
import csv
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vajra.weather import synthetic_leh
from vajra.api import default_design, MATERIALS, GLAZING
from vajra.solver import simulate

root = Path(__file__).resolve().parents[1]
r = simulate(default_design(), synthetic_leh(3), MATERIALS, GLAZING, 10, "free")
out = root / "exports" / "ansys" / "python_wall_results.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["timestamp","inner_surface_c"])
    for t, temp in zip(r["series"]["time"], r["series"]["t_air_in_c"]): w.writerow([t, temp])
print(out)
