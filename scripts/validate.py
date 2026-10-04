from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np


def validate(measured: Path, simulated: Path):
    m = pd.read_csv(measured, parse_dates=["timestamp"]).set_index("timestamp")
    s = pd.read_csv(simulated, parse_dates=["timestamp"]).set_index("timestamp")
    x = m.join(s, lsuffix="_measured", rsuffix="_simulated").dropna()
    err = x["t_in_simulated"] - x["t_in_measured"]
    rmse = float(np.sqrt(np.mean(err**2)))
    mae = float(np.mean(np.abs(err)))
    mean_m = float(x["t_in_measured"].mean())
    nmbe = float(np.sum(err) / max(1, len(err)) / max(1e-9, mean_m) * 100)
    cv = float(rmse / max(1e-9, mean_m) * 100)
    print(f"RMSE_C={rmse:.4f}\nMAE_C={mae:.4f}\nNMBE_percent={nmbe:.4f}\nCV_RMSE_percent={cv:.4f}")
