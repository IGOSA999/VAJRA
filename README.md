# VAJRA

A thermal model for designing passive shelters in cold, sunny places such as Ladakh. You describe a shelter and give it hourly weather. VAJRA predicts the indoor air temperature, the solar energy the shelter gains, and where its heat leaks out. It can also compare designs on the same weather and rank them by how much heating they would need.

Built by Team VAJRA for Smart India Hackathon 2026, problem statement PS26051: *Software Based Model Development for Design of Area Specific Shelter for Thermal Comfort Maintenance*.

## The problem

Leh gets about 300 clear days a year and strong sun. Shelters there warm up during the day, then fall close to the outside temperature after sunset because heat escapes through walls, roof, floor and openings. People make up the difference with fuel. A shelter designed for its own climate (the right materials, thickness, orientation, windows and thermal mass) can keep more of the daytime heat and need less of that fuel.

Choosing those things by guesswork is hard, so VAJRA calculates the result for each choice and lets you compare them.

## What it does

- **Indoor temperature.** Hourly indoor air temperature for a chosen period, next to the outside temperature.
- **Solar energy.** Sunlight falling on each facade and the roof, how much passes through the glazing, and how much the opaque surfaces absorb.
- **Heat flow.** Heat gained or lost through each wall, the roof, the floor, the glazing and ventilation, with totals in kWh.
- **Heating demand.** Every design is also run with an ideal heater that holds a set temperature. The energy that heater needs is the main number used to rank designs.
- **Design comparison.** One table runs the current design against several candidates on the same weather. A second table changes only the wall material.
- **Your own inputs.** Size, roof, orientation, wall, roof and floor layers, windows, night cover, ventilation, and thermal mass (water or phase change material) are all editable. Weather can come from the bundled Leh file or an uploaded CSV.
- **Section drawing and design sheet.** A to-scale section of the chosen design and a one-page printable sheet.
- **ANSYS export.** A wall-panel case for a transient thermal check in ANSYS.

## How it works

Each wall, roof and floor is a stack of layers solved with one-dimensional transient conduction, so heat stored during the day is released at night. The outside surface exchanges heat by convection, absorbed sunlight and radiation to the sky. Indoor air is a heat balance that includes ventilation, solar gain through glazing, the floor and any interior mass. The floor couples to a soil column. Solar position and irradiance on tilted surfaces come from pvlib, with a built-in fallback. Air density is taken from the site pressure, which matters at 3,500 m.

The model is physics based. There is no machine learning in it.

## Run it

You need Python 3.12.

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

If PowerShell refuses to activate the environment, run `Set-ExecutionPolicy -Scope Process Bypass` first.

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Then open <http://127.0.0.1:8000>. Fonts, the plotting library and the real Leh weather file are in the repository, so the app runs without internet once it is installed.

A page load runs the model for the coldest 14 days of the bundled year. Run, Compare designs and Compare wall materials each run the solver again with the settings on the page. Times depend on your machine; on a small hosted instance they can be much longer.

## Weather data

`data/weather/leh_2024_hourly.csv` is an hourly NASA POWER series for Leh (34.15° N, 77.58° E, 3,500 m). To fetch another place or year, use `python scripts/fetch_weather.py` on a machine with internet. To use your own data, upload a CSV in the dashboard. It needs an ISO 8601 `timestamp` column, `t_air_c` and `ghi_wm2`. Wind, pressure, longwave and diffuse or direct irradiance columns are optional. See `data/weather/README.txt` for the details.

## Materials

`data/materials.csv` and `data/glazing.csv` hold the layer and glazing properties. Every row names its source and says whether the value is typical or measured. Most are typical handbook or datasheet values. Check them against the actual product before relying on a result for a real build.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests check the solver against independent answers: steady-state U-value, an analytic slab solution, a lumped thermal-mass limit, energy balance at the boundaries, time-step convergence, start-up independence, and the direction of known effects (more insulation lowers heating demand, and so on). Web tests cover the API and the page. `python scripts/endpoint_times.py` prints how long each endpoint takes on your machine.

## ANSYS check

`exports/ansys/` holds a transient wall-panel case generated from a design: an APDL macro, boundary tables, the layer properties, and the Python reference series. `docs/ANSYS_RUN.md` records one run in ANSYS Student and the difference from the Python solver (maximum 2.22 °C, RMS 1.44 °C over the comparison points). That compares one wall panel, not a whole shelter, and it is not a comparison with measurements.

## Project layout

```
vajra/       solver, weather loading, solar geometry, optimiser, API, report
web/         dashboard (plain HTML, CSS, JavaScript), fonts, plotting library
data/        weather file, material and glazing tables
exports/     ANSYS wall-panel case
scripts/     weather fetch, ANSYS comparison, validation, timing, UI checks
tests/       verification and web tests
docs/        data contract, ANSYS notes, demo script
```

## What it does not do

- It has not been compared with a measured shelter. Treat every output as a model estimate. There is no accuracy figure for it yet.
- No airflow simulation (CFD), moisture or condensation, snow load, or structural design.
- No cost, payback or fuel-saving claims.
- The comfort band (15 to 28 °C by default) is a placeholder you set, not a standard.
- Some defaults are assumptions: 70% of transmitted sunlight lands on the floor and interior mass, soil properties, and the wind scaling exponent.
- A validation script (`scripts/validate.py`) is ready for sensor logs from a test shelter, but no field data exists yet.

## License

MIT. See `LICENSE`. The bundled IBM Plex and Source Serif fonts are under the SIL Open Font License (`web/fonts/OFL.txt`).
