# VAJRA

## What it is
VAJRA is a physics-based transient thermal model for area-specific shelter design at Leh. It simulates a layered shelter against hourly weather, solar input, ventilation, ground coupling and an ideal-heater case, then compares alternative designs. The prototype also prepares a Level-A ANSYS wall-panel case for an independent conduction check.

The outputs are model estimates. The prototype is not validated against measured shelter data, and it does not make cost, payback, fuel-efficiency or full-shelter ANSYS accuracy claims.

## Run locally
```text
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```
Open `http://127.0.0.1:8000`.

## Test
Install the development requirements, then run:
```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/slop_scan.py
```
For endpoint timing evidence, use `python scripts/endpoint_times.py`.

## What it does not do yet
VAJRA does not model CFD airflow, moisture or condensation, structural design, snow load, cost, payback, fuel efficiency or measured-data validation. Material properties and the comfort band remain project inputs that should be verified before a judged presentation.

The live demo uses Render's Free plan. The Free plan has 0.1 CPU and sleeps after 15 minutes of inactivity, so the first request after sleep can take about a minute. The project is designed to run locally with the commands above when the real Leh weather file is present.
