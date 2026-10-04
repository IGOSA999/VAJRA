# VAJRA data contract

## Design
```json
{
  "name": "baseline_block",
  "site": {"lat": 34.1526, "lon": 77.5771, "elevation_m": 3500},
  "geometry": {
    "length_m": 4.0,
    "width_m": 3.0,
    "wall_height_m": 2.4,
    "roof": {"type": "mono_pitch", "pitch_deg": 15, "high_side": "N"},
    "azimuth_deg": 180
  },
  "constructions": {
    "wall": [{"material": "stone_masonry", "mm": 300}],
    "roof": [{"material": "mineral_wool", "mm": 100}, {"material": "timber", "mm": 25}],
    "floor": [{"material": "concrete_dense", "mm": 100}],
    "ground": {"soil_depth_m": 2.0}
  },
  "openings": [{
    "facade": "main", "width_m": 1.8, "height_m": 1.2,
    "glazing": "double_clear",
    "night_cover": {"r_m2k_per_w": 0.8, "from_hour": 17, "to_hour": 9}
  }],
  "air": {"infiltration_ach": 0.5, "vent_ach": 0.0, "vent_hours": [11, 15]},
  "internal_gains_w": 0,
  "solar_split": {"floor_and_mass": 0.7},
  "comfort": {"low_c": 15, "high_c": 28},
  "setpoint_c": 15
}
```

## Weather frame
Hourly UTC rows with `t_air_c`, `rh_pct`, `wind10_ms`, `pressure_kpa`, `ghi_wm2`, `dhi_wm2`, `dni_wm2`, `lw_down_wm2`. Metadata carries source, coordinates, elevation, synthetic flag and missing hour count.

## Result
The API returns `meta`, `series` and `summary`. Series are at the solver time step and include indoor and outdoor temperature, GHI, total solar input, heat flow by building element and heater power. Summary includes extrema, comfort hours, degree-hours below the lower comfort limit, overheating hours, heating energy and solar and flow totals.
