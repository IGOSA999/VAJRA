# VAJRA data contract

## Design

The design object contains site coordinates and elevation, geometry, layered wall/roof/floor constructions, openings, air exchange, internal gains, solar split, comfort band, setpoint, ground reflectance and optional interior thermal mass.

## Weather

The weather frame is hourly UTC data with air temperature and global irradiance plus optional humidity, wind, pressure, diffuse irradiance, direct irradiance and longwave downwelling radiation. Metadata identifies provider, year, site and hour coverage. Uploaded site weather must provide latitude, longitude and elevation.

## Result

The API returns `meta`, `series` and `summary`. Series contain indoor and outdoor temperatures, GHI, transmitted solar input, heat flow by element, heater power, IST timestamps and a night mask. Summary values include temperature extrema, comfort metrics, heating energy, solar totals, heat-flow totals and numerical balance diagnostics.

## Background jobs

The dashboard uses `/api/jobs/default`, `/api/jobs/run`, `/api/jobs/compare` and `/api/jobs/materials`. Poll `/api/jobs/{id}` for real progress and partial rows. A missing job after restart is reported as lost rather than as an empty result.
