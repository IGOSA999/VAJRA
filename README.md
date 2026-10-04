# VAJRA thermal shelter model

## What it is
VAJRA is a physics-based transient thermal model for area-specific shelter design. It uses hourly weather, a layered shelter construction, solar input, ventilation, ground coupling and an ideal heater run. It reports indoor air temperature, solar energy and heat flow by element. The comparison view samples wall materials and other design variables on the same weather file, and a material-only view holds the other settings fixed. Water and paraffin PCM are available as interior thermal mass options.

The outputs are model estimates. The prototype has not been compared with a measured shelter.

## How to run it
Use Python 3.11 or newer.

`python -m pip install -r requirements.txt`

`python run.py`

Open `http://127.0.0.1:8000`.

## How to test it
`python -m pytest -q`

`python scripts/slop_scan.py`

The repair review tests are in `tests/test_fix_prompt.py`. The screenshot checks use `scripts/screenshots.py` at 1440x900 and 390x844 and record font loading in `font_status.json`.

The test suite uses Starlette TestClient, which requires `httpx2` in current Starlette releases. The release pins the tested dependency set in `requirements.txt`, including `httpx2==2.13.1`. A real Leh weather file is fetched with `python scripts/fetch_weather.py` on a machine with internet access. Until then, development tests use clearly labelled synthetic test data.

## What it does not do yet
It does not model CFD airflow patterns, moisture, condensation, snow load, structural design, cost, payback, fuel efficiency, accuracy claims or measured shelter validation. The Level-A ANSYS wall-panel case was run in ANSYS Student 2026 R1. Comparison against the Python wall inner-surface series over 4021 points gave a maximum absolute difference of 2.218076 C and an RMS difference of 1.437016 C. This is a wall-panel cross-check, not full-shelter validation. A full-year pvlib cross-check has been run by the team in a clean environment. South-wall annual plane-of-array total differed by about 0.3% from pvlib, while the printed hourly MAPE was about 3.3%. The acceptance criterion is the annual total, with a 1% limit. The current sandbox cannot reproduce that run because pvlib is not installed here.


## Web dashboard resolution
The dashboard uses hourly solver steps for interactive runs and comparisons. The core solver tests include the required 10-minute transient cases. The dashboard default is a 14-day Leh window, with 30-day and full-year options.

The dashboard design comparison is an interactive seven-row comparison: the named baseline plus six seeded candidates. The formal two-stage optimiser remains available in `vajra/optimise.py` for the documented 1000-design screening workflow.
