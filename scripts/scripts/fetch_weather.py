from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vajra.weather import fetch_nasa_power

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "data" / "weather" / "leh_2024_hourly.csv"
fetch_nasa_power(34.1526, 77.5771, "20240101", "20241231", out)
print(out)
