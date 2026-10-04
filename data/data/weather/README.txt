# Weather data

The bundled `leh_2024_hourly.csv` file is a NASA POWER hourly weather series for Leh, Ladakh. The dashboard shows the provider, year, site and hourly coverage, and the default 14-day view uses the coldest contiguous 14-day window.

A user CSV may be uploaded through the dashboard. It must contain an ISO 8601 `timestamp` column plus `t_air_c` and `ghi_wm2`; optional solar, wind, pressure and longwave columns are accepted. For a custom site, include one `latitude`, one `longitude` and one `elevation_m` value so the solar calculation uses the uploaded site's location.
