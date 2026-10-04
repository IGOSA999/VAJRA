from pathlib import Path
import pandas as pd
from vajra.weather import load_weather_csv


def test_t09_portability(tmp_path: Path):
    path = tmp_path / "custom.csv"
    idx = pd.date_range("2025-01-01", periods=6, freq="h", tz="UTC")
    pd.DataFrame({"timestamp": idx, "t_air_c": [-5,-4,-3,-4,-6,-7], "ghi_wm2": [0,50,200,100,0,0]}).to_csv(path, index=False)
    wf = load_weather_csv(path)
    assert len(wf.frame) == 6
    assert wf.meta["synthetic"] is False
