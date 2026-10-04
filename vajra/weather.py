from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import csv
from datetime import datetime, timezone

import numpy as np
import pandas as pd


PARAMS = [
    "T2M", "RH2M", "WS10M", "PS", "ALLSKY_SFC_SW_DWN",
    "ALLSKY_SFC_SW_DIFF", "ALLSKY_SFC_SW_DNI", "ALLSKY_SFC_LW_DWN",
]

COLUMN_MAP = {
    "T2M": "t_air_c",
    "RH2M": "rh_pct",
    "WS10M": "wind10_ms",
    "PS": "pressure_kpa",
    "ALLSKY_SFC_SW_DWN": "ghi_wm2",
    "ALLSKY_SFC_SW_DIFF": "dhi_wm2",
    "ALLSKY_SFC_SW_DNI": "dni_wm2",
    "ALLSKY_SFC_LW_DWN": "lw_down_wm2",
}


@dataclass
class WeatherFrame:
    frame: pd.DataFrame
    meta: dict

    @property
    def start(self):
        return self.frame.index[0]

    @property
    def end(self):
        return self.frame.index[-1]


def synthetic_leh(days: int = 14) -> WeatherFrame:
    idx = pd.date_range("2024-01-01", periods=24 * days, freq="h", tz="UTC")
    doy = idx.dayofyear.to_numpy()
    hour = idx.hour.to_numpy() + idx.minute.to_numpy() / 60
    seasonal = -8 + 10 * np.sin(2 * np.pi * (doy - 80) / 365)
    diurnal = 7 * np.sin(2 * np.pi * (hour - 14) / 24)
    t_air = seasonal + diurnal
    from .solar import solar_position
    zen, _ = solar_position(idx, 34.1526, 77.5771)
    sun = np.maximum(0.0, np.sin(np.pi * (hour - 2) / 10))
    ghi = 720 * sun ** 1.25
    dhi = 0.25 * ghi
    cosz = np.cos(np.radians(zen))
    dni = np.where(cosz > 0.05, np.maximum(ghi - dhi, 0) / np.maximum(cosz, 0.05), 0.0)
    lw = 240 + 18 * np.clip((t_air + 20) / 40, 0, 1)
    frame = pd.DataFrame({
        "t_air_c": t_air,
        "rh_pct": np.full(len(idx), 25.0),
        "wind10_ms": 2.0 + 1.5 * (1 - sun),
        "pressure_kpa": 66.0,
        "ghi_wm2": ghi,
        "dhi_wm2": dhi,
        "dni_wm2": dni,
        "lw_down_wm2": lw,
    }, index=idx)
    return WeatherFrame(frame, {
        "source": "synthetic test data",
        "lat": 34.1526, "lon": 77.5771, "elevation_m": 3500,
        "synthetic": True, "missing_hours": 0,
    })


def load_weather_csv(path: Path) -> WeatherFrame:
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise ValueError(f"Could not read weather CSV: {exc}") from exc
    if "timestamp" not in df.columns:
        raise ValueError("Weather CSV needs an ISO 8601 timestamp column named timestamp")
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if ts.isna().any():
        bad = int(np.flatnonzero(ts.isna())[0])
        raise ValueError(f"Invalid timestamp at row {bad + 2}")
    required = {"t_air_c", "ghi_wm2"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required weather columns: {', '.join(missing)}")
    out = pd.DataFrame(index=ts)
    out["t_air_c"] = pd.to_numeric(df["t_air_c"], errors="coerce").to_numpy()
    out["ghi_wm2"] = pd.to_numeric(df["ghi_wm2"], errors="coerce").to_numpy()
    defaults = {
        "rh_pct": 25.0, "wind10_ms": 2.0, "pressure_kpa": 66.0,
        "dhi_wm2": np.nan, "dni_wm2": np.nan, "lw_down_wm2": np.nan,
    }
    for c, default in defaults.items():
        out[c] = pd.to_numeric(df[c], errors="coerce").to_numpy() if c in df.columns else default
    out = out.sort_index()
    if out["t_air_c"].isna().any() or out["ghi_wm2"].isna().any():
        bad = out.index[out[["t_air_c", "ghi_wm2"]].isna().any(axis=1)][0]
        raise ValueError(f"Required weather value missing at timestamp {bad.isoformat()}")
    if out["dhi_wm2"].isna().any() or out["dni_wm2"].isna().any():
        from .solar import erbs_decompose
        dhi, dni = erbs_decompose(out["ghi_wm2"].to_numpy(), ts)
        out["dhi_wm2"] = np.where(out["dhi_wm2"].isna(), dhi, out["dhi_wm2"])
        out["dni_wm2"] = np.where(out["dni_wm2"].isna(), dni, out["dni_wm2"])
    out["lw_down_wm2"] = out["lw_down_wm2"].interpolate().bfill().ffill().fillna(240.0)
    return WeatherFrame(out, {
        "source": str(path.name), "lat": None, "lon": None, "elevation_m": None,
        "synthetic": False, "missing_hours": int(out.isna().any(axis=1).sum()),
    })


def select_window(weather: WeatherFrame, days: int | None) -> WeatherFrame:
    if days is None:
        return weather
    if days <= 0:
        raise ValueError("Weather window must be positive")
    frame = weather.frame.sort_index()
    start = frame.index[0]
    end = start + pd.Timedelta(days=days)
    window = frame.loc[(frame.index >= start) & (frame.index < end)].copy()
    if window.empty:
        raise ValueError("Weather file does not contain the requested period")
    return WeatherFrame(window, dict(weather.meta))


def fetch_nasa_power(lat: float, lon: float, start: str, end: str, output: Path) -> Path:
    query = urlencode({
        "parameters": ",".join(PARAMS), "community": "RE", "longitude": lon,
        "latitude": lat, "start": start, "end": end, "format": "CSV", "time-standard": "UTC",
    })
    url = "https://power.larc.nasa.gov/api/temporal/hourly/point?" + query
    try:
        with urlopen(url, timeout=30) as response:
            text = response.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"NASA POWER request failed: {exc}") from exc
    lines = text.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("YEAR,MO,DY,HR")), None)
    if header_idx is None:
        raise RuntimeError("NASA POWER response did not contain the expected hourly CSV header")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def load_nasa_csv(path: Path, lat: float, lon: float, elevation_m: float = 3500.0) -> WeatherFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("YEAR,MO,DY,HR")), None)
    if header_idx is None:
        raise ValueError("NASA file does not contain an hourly data header")
    rows = list(csv.DictReader(lines[header_idx:]))
    records = []
    for row in rows:
        year, month, day, hour = int(row["YEAR"]), int(row["MO"]), int(row["DY"]), int(row["HR"])
        stamp = pd.Timestamp(datetime(year, month, day, hour, tzinfo=timezone.utc))
        record = {"timestamp": stamp}
        for p, c in COLUMN_MAP.items():
            raw = row.get(p, "")
            record[c] = np.nan if raw in ("", "-999") else float(raw)
        records.append(record)
    df = pd.DataFrame(records).set_index("timestamp")
    missing = int(df.isna().any(axis=1).sum())
    if df["dhi_wm2"].isna().any() or df["dni_wm2"].isna().any():
        from .solar import erbs_decompose
        dhi, dni = erbs_decompose(df["ghi_wm2"].fillna(0).to_numpy(), df.index)
        df["dhi_wm2"] = df["dhi_wm2"].fillna(pd.Series(dhi, index=df.index))
        df["dni_wm2"] = df["dni_wm2"].fillna(pd.Series(dni, index=df.index))
    return WeatherFrame(df, {
        "source": path.name, "lat": lat, "lon": lon, "elevation_m": elevation_m,
        "synthetic": False, "missing_hours": missing,
    })
