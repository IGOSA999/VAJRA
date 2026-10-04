import numpy as np
import pandas as pd
from vajra.api import default_design, MATERIALS, GLAZING
from vajra.solver import simulate
from vajra.weather import WeatherFrame


def test_t10_spinup_independence():
    idx = pd.date_range("2024-01-01", periods=8*24, freq="h", tz="UTC")
    frame = pd.DataFrame({
        "t_air_c": np.full(len(idx), -5.0), "rh_pct": np.full(len(idx), 30.0),
        "wind10_ms": np.full(len(idx), 1.0), "pressure_kpa": np.full(len(idx), 66.0),
        "ghi_wm2": np.zeros(len(idx)), "dhi_wm2": np.zeros(len(idx)),
        "dni_wm2": np.zeros(len(idx)), "lw_down_wm2": np.full(len(idx), 210.0),
    }, index=idx)
    meta = {"source":"constant fixture","lat":34.15,"lon":77.58,"elevation_m":3500,"synthetic":True,"missing_hours":0}
    d = default_design()
    d["constructions"]["wall"] = [{"material":"mineral_wool","mm":100}]
    d["constructions"]["roof"] = [{"material":"mineral_wool","mm":100}]
    d["constructions"]["floor"] = [{"material":"eps","mm":50}]
    d["openings"] = []
    a = simulate(d, WeatherFrame(frame, meta), MATERIALS, GLAZING, 30, "free")
    pre = frame.iloc[:72].copy()
    pre.index = pre.index - pd.Timedelta(days=3)
    b = simulate(d, WeatherFrame(pd.concat([pre, frame]), meta), MATERIALS, GLAZING, 30, "free")
    sa = pd.Series(a["series"]["t_air_in_c"], index=pd.to_datetime(a["series"]["time"], utc=True))
    sb = pd.Series(b["series"]["t_air_in_c"], index=pd.to_datetime(b["series"]["time"], utc=True))
    joined = pd.concat([sa, sb], axis=1).dropna()
    assert float((joined.iloc[:,0] - joined.iloc[:,1]).abs().max()) < 0.05
