from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable

import numpy as np

try:
    import pvlib  # type: ignore
    PVLIB_AVAILABLE = True
except Exception:
    pvlib = None
    PVLIB_AVAILABLE = False


def _julian_day(dt: datetime) -> float:
    if dt.tzinfo is None:
        raise ValueError("Datetime needs a timezone")
    utc = dt.astimezone(__import__("datetime").timezone.utc)
    return utc.timestamp() / 86400.0 + 2440587.5


def solar_position(index: Iterable, latitude_deg: float, longitude_deg: float) -> tuple[np.ndarray, np.ndarray]:
    # NOAA-style solar position approximation. It is used only as a fallback when pvlib is unavailable.
    times = list(index)
    zenith, azimuth = [], []
    lat = math.radians(latitude_deg)
    for stamp in times:
        dt = stamp.to_pydatetime() if hasattr(stamp, "to_pydatetime") else stamp
        jd = _julian_day(dt)
        t = (jd - 2451545.0) / 36525.0
        geom_mean_long = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
        geom_mean_anom = math.radians(357.52911 + t * (35999.05029 - 0.0001537 * t))
        ecc = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
        eq_center = (math.sin(geom_mean_anom) * (1.914602 - t * (0.004817 + 0.000014 * t))
                     + math.sin(2 * geom_mean_anom) * (0.019993 - 0.000101 * t)
                     + math.sin(3 * geom_mean_anom) * 0.000289)
        sun_true_long = geom_mean_long + eq_center
        omega = math.radians(125.04 - 1934.136 * t)
        app_long = math.radians(sun_true_long - 0.00569 - 0.00478 * math.sin(omega))
        obliq = math.radians(23 + 26 / 60 + 21.448 / 3600 - 46.815 / 3600 * t - 0.00059 / 3600 * t**2 + 0.001813 / 3600 * t**3)
        decl = math.asin(math.sin(obliq) * math.sin(app_long))
        var_y = math.tan(obliq / 2) ** 2
        ecc_time = 4 * math.degrees(var_y * math.sin(2 * math.radians(geom_mean_long))
                                    - 2 * ecc * math.sin(geom_mean_anom)
                                    + 4 * ecc * var_y * math.sin(geom_mean_anom) * math.cos(2 * math.radians(geom_mean_long))
                                    - 0.5 * var_y**2 * math.sin(4 * math.radians(geom_mean_long))
                                    - 1.25 * ecc**2 * math.sin(2 * geom_mean_anom))
        utc_minutes = dt.hour * 60 + dt.minute + dt.second / 60
        true_solar_minutes = (utc_minutes + ecc_time + 4 * longitude_deg) % 1440
        hour_angle = math.radians(true_solar_minutes / 4 - 180 if true_solar_minutes / 4 >= 0 else true_solar_minutes / 4 + 180)
        cos_zen = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(hour_angle)
        zen = math.degrees(math.acos(max(-1, min(1, cos_zen))))
        cos_az_num = math.sin(hour_angle)
        cos_az_den = math.cos(hour_angle) * math.sin(lat) - math.tan(decl) * math.cos(lat)
        az = (math.degrees(math.atan2(cos_az_num, cos_az_den)) + 180) % 360
        zenith.append(zen)
        azimuth.append(az)
    zen = np.asarray(zenith, dtype=float)
    az = np.asarray(azimuth, dtype=float)
    # Convert geometric zenith to apparent zenith using the NOAA atmospheric refraction correction.
    elevation = 90.0 - zen
    refr = np.zeros_like(elevation)
    m1 = (elevation >= 5.0) & (elevation <= 85.0)
    tan_e = np.tan(np.radians(elevation[m1]))
    refr[m1] = (58.1 / tan_e - 0.07 / tan_e**3 + 0.000086 / tan_e**5) / 3600.0
    m2 = (elevation > -0.575) & (elevation < 5.0)
    e = elevation[m2]
    refr[m2] = (1735.0 + e * (-518.2 + e * (103.4 + e * (-12.79 + e * 0.711)))) / 3600.0
    return np.asarray(zen - refr), az


def extraterrestrial_irradiance(index) -> np.ndarray:
    doy = np.asarray([x.dayofyear for x in index], dtype=float)
    return 1367.0 * (1 + 0.033 * np.cos(np.radians(360 * doy / 365.0)))


def erbs_decompose(ghi: np.ndarray, index) -> tuple[np.ndarray, np.ndarray]:
    ghi = np.maximum(np.asarray(ghi, dtype=float), 0)
    # Erbs needs the solar zenith to form the clearness index.
    lat = 0.0
    lon = 0.0
    if hasattr(index, "attrs"):
        lat = float(index.attrs.get("lat", 0.0))
        lon = float(index.attrs.get("lon", 0.0))
    zen, _ = solar_position(index, lat, lon)
    cosz = np.maximum(np.cos(np.radians(zen)), 0.0)
    etr = extraterrestrial_irradiance(index)
    kt = ghi / np.maximum(etr * np.maximum(cosz, 0.065), 1e-6)
    kd = np.where(kt <= 0.22, 1 - 0.09 * kt,
         np.where(kt <= 0.8, 0.9511 - 0.1604*kt + 4.388*kt**2 - 16.638*kt**3 + 12.336*kt**4,
                  0.165))
    dhi = np.clip(kd * ghi, 0, ghi)
    dni = np.divide(np.maximum(ghi - dhi, 0), np.maximum(cosz, 0.05))
    return dhi, dni


def _hay_davies(tilt_deg, azimuth_deg, dhi, dni, dni_extra, zenith, solar_azimuth, aoi, albedo=0.2):
    cosz = np.cos(np.radians(zenith))
    rb = np.divide(np.cos(np.radians(aoi)), np.maximum(cosz, 1e-3))
    rb = np.maximum(rb, 0)
    anisotropy = np.divide(dni, np.maximum(dni_extra, 1e-6))
    sky_iso = (1 - anisotropy) * (1 + math.cos(math.radians(tilt_deg))) / 2
    sky = dhi * (anisotropy * rb + sky_iso)
    beam = np.maximum(dni * np.cos(np.radians(aoi)), 0)
    ground = albedo * np.maximum(dhi + np.maximum(dni * cosz, 0), 0) * (1 - math.cos(math.radians(tilt_deg))) / 2
    return np.maximum(beam + sky + ground, 0)


def plane_of_array_fallback(tilt_deg: float, azimuth_deg: float, index, ghi, dhi, dni, lat, lon, albedo=0.2) -> np.ndarray:
    zen, saz = solar_position(index, lat, lon)
    aoi_cos = (np.cos(np.radians(zen)) * math.cos(math.radians(tilt_deg))
               + np.sin(np.radians(zen)) * math.sin(math.radians(tilt_deg)) * np.cos(np.radians(saz - azimuth_deg)))
    aoi = np.degrees(np.arccos(np.clip(aoi_cos, -1, 1)))
    return _hay_davies(tilt_deg, azimuth_deg, dhi, dni, extraterrestrial_irradiance(index), zen, saz, aoi, albedo=albedo)


def plane_of_array(tilt_deg: float, azimuth_deg: float, index, ghi, dhi, dni, lat, lon, albedo=0.2) -> np.ndarray:
    if PVLIB_AVAILABLE:
        import pandas as pd
        index = pd.DatetimeIndex(list(index))
        pos = pvlib.solarposition.get_solarposition(index, lat, lon)
        zen = pos["apparent_zenith"].to_numpy()
        saz = pos["azimuth"].to_numpy()
        dni_extra = np.asarray(pvlib.irradiance.get_extra_radiation(index), dtype=float)
        total = pvlib.irradiance.get_total_irradiance(
            tilt_deg, azimuth_deg, zen, saz, np.maximum(dni, 0), np.maximum(ghi, 0), np.maximum(dhi, 0),
            dni_extra=dni_extra, albedo=albedo, model="haydavies")
        return np.maximum(np.asarray(total["poa_global"], dtype=float), 0)
    return plane_of_array_fallback(tilt_deg, azimuth_deg, index, ghi, dhi, dni, lat, lon, albedo)
