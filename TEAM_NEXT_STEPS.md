# VAJRA team handoff

The latest patch keeps the stage-2 baseline in the full-period confirmation and adds a regression test for that rule.

## 1. Clean release check on Windows

Use a fresh environment from the project root. In PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/slop_scan.py
```

In Command Prompt, activate with `.venv\Scripts\activate.bat` instead. Do not use `Activate.ps1` from Command Prompt. The current Starlette TestClient also requires `httpx2`, which is now pinned in `requirements.txt` as `httpx2==2.13.1`.

Record the pytest count exactly as printed. Do not replace a skipped pvlib test with a pass.

## 2. Fetch real Leh weather

With internet access:

```powershell
python scripts/fetch_weather.py
```

Expected output file:

```text
data/weather/leh_2024_hourly.csv
```

Then start the app:

```powershell
python run.py
```

Open `http://127.0.0.1:8000`. The weather provenance shown by the app should identify the real NASA POWER file. Do not call synthetic output a Leh result.

## 3. Verify the pvlib comparison

The clean environment should have pvlib installed from `requirements.txt`. Run the full test suite. The full-year cross-check is in `tests/test_fix_prompt.py` and prints the solar elevation difference, hourly POA MAPE and annual south-wall total ratio.

The current project acceptance rule is annual south-wall POA total within 1% of pvlib. The hourly MAPE remains diagnostic output.

## 4. Run the ANSYS Level A case

Start the app and load/run the desired design. Click:

`Prepare ANSYS files`

This writes files under:

```text
exports/ansys/
```

The current export includes `boundary_conditions.csv`, `materials.csv`, `wall_panel.mac`, two tab-delimited APDL table files, and `python_wall_results.csv`. Open `wall_panel.mac` in the installed ANSYS Mechanical APDL version with the working directory set to `exports/ansys`. The macro uses SOLID278 and builds the exact exported wall-layer stack. Run the wall-panel case, let the macro write `ansys_wall_results.csv`, then run:

```powershell
python scripts/compare_ansys.py
```

Record the printed `max_abs_difference_c` and `rms_difference_c`. Put those real values on the presentation. Do not claim agreement before the ANSYS run exists.

## 5. Before presentation

Agree the project comfort band and state that it is a project input, not a cited standard. Keep the existing disclaimer that model outputs are estimates and that the solver has not been validated against a measured shelter.

Do not present the synthetic-weather material ranking as a real-climate finding. Do not present the unmet 1000-design/60-second target as achieved.
