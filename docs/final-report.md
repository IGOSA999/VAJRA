# VAJRA final build report

Date: 3 October 2026  
Problem statement: Smart India Hackathon 2026, PS26051

## 1. How to start it

```text
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:8000`.

## 2. Review-fix status

| Item | Status | Tests and evidence |
|---|---|---|
| 1. Clean install | Fixed by code/config | `python-multipart>=0.0.20` is declared in `requirements.txt` and `pyproject.toml`. The team reports a clean-environment install succeeded. This sandbox cannot reproduce package installation because outbound package access is blocked. |
| 2. Water and PCM | Fixed | Water and PCM regression tests passed in the team's reviewed build. Seven-day synthetic fixture: 3.1236 K no mass versus 3.0551 K with 500 kg water. PCM minimum: -10.7396 C without latent heat versus -10.7172 C with 200 kJ/kg latent heat. Maximum boundary closure ratio: 6.11e-15. Maximum PCM iterations: 2. Unsupported design keys are rejected. |
| 3. Insulation side | Fixed | `test_fix_03_outside_insulation_smaller_swing` passed. Seven-day synthetic fixture: 5.3589 K with 100 mm outside insulation versus 9.9180 K with the same insulation inside. |
| 4. Sweep, material comparison and finalist selection | Partly fixed | The seeded Latin-hypercube candidate generator covers all 24 wall-material/insulation combinations in the first 24 candidates. Same-seed rankings are deterministic. Material-only comparison produces distinct heating estimates. The stage-2 baseline omission found in this review was reproduced and fixed: the selection now keeps the baseline plus the best 20 non-baseline candidates. Targeted integration smoke: 21 confirmed rows, including the baseline and 20 non-baseline designs. The 1000-design/60 s target remains unmet. |
| 5. Fonts | Fixed | Four WOFF2 files are bundled. `slop_scan.py` passes and the screenshot harness reported the bundled IBM Plex Sans, IBM Plex Mono and Source Serif 4 fonts loaded at 1440x900 and 390x844. |
| 6. Energy balance | Fixed | Independent boundary-flow criterion is used for T2. Reproduced pre-fix closure was 1.5963% on the four-day heater fixture; after the fix it was 6.11e-15. Equation-level residual was below 1e-9. |
| 7. pvlib cross-check | Fixed with team-side execution | The conditional full-year comparison exists. In the team's clean environment, solar elevation differed from pvlib by at most about 0.01 degrees above 5 degrees elevation. South-wall annual POA total differed by about 0.3%. Printed hourly MAPE was about 3.3%. The accepted criterion is annual total within 1%; hourly MAPE is retained as diagnostic output. This result was not reproduced in the current sandbox because pvlib is unavailable here. |
| 8. Report accuracy | Fixed | The previous reviewed build had 22 collected tests: 21 passed and 1 skipped when run file-isolated. The current repository contains 28 test functions, including the stage-2 baseline-selection regression, three web API regressions, and two dashboard-window regressions. The user-side clean run before this final web integration reported 23 passed. In this final integration pass, 11 targeted tests passed, `python -m compileall -q vajra tests` passed, and `scripts/slop_scan.py` passed. A full 28-test run was not completed here because the suite exceeded the sandbox execution window. |

## 3. Original verification tests

The existing T1 to T11 test files were each run separately after the fixes. Results:

- T1: passed
- T2: passed
- T3: passed
- T4: passed
- T5: passed
- T6: passed
- T7: passed
- T8: passed
- T9: passed
- T10: passed
- T11 ANSYS export: passed

The repair regression file contains twelve executable tests plus one conditional pvlib test. The web repair adds three API tests and two dashboard-window regression tests. The repository therefore contains 28 executable or conditional tests in total.

## 4. Solver changes made

The solver now validates the design structure before simulation and rejects unsupported fields. Interior water is represented as sensible thermal storage. Paraffin PCM uses the apparent heat-capacity method over the declared melting range and iterates the mass temperature to a 0.01 K change criterion. The soil column is part of the implicit thermal domain used for the independent energy check.

The sweep writes wall layers in outside-to-inside order. Wall material is a sampled variable. Material-only comparison is available at `/api/compare-materials` and in the dashboard.

The 10 and 15 minute verification cases use two backward-Euler substeps for the convergence check. The requested timestep remains recorded in the result metadata, with the actual integration timestep recorded separately.

## 5. Post-v3 corrective review

The stage-2 confirmation code originally used `screening[:21]`. That is not equivalent to the required baseline-plus-best-20 rule because the baseline can sort below the first 21 screened candidates. The defect was reproduced before editing: with the baseline placed at rank 26, the pre-patch selection excluded it.

The code now selects the named baseline explicitly and appends the best 20 non-baseline candidates. The targeted integration check reported 21 confirmation rows, with 1 baseline and 20 non-baseline designs. The permanent regression test `test_fix_04_stage_2_always_keeps_baseline` passed.

`python -m compileall -q vajra tests` passed after the change. `python scripts/slop_scan.py` passed.

## 6. Visual checks

The dashboard was rendered at 1440x900 and 390x844 after the bundled font update. The 1440 view shows the temperature plot, to-scale shelter section, heat-flow chart, metrics, design comparison and wall-material comparison. The 390 view keeps the controls and results in one column.

`python scripts/slop_scan.py` passed.

The sandbox browser blocks direct navigation to the local loopback server. The screenshot harness therefore embeds the same local API payloads and bundled font bytes into the rendered page. This is recorded as a harness limitation, not as an application networking result.

## 7. Untested or assumed

The bundled Leh weather file has not been fetched from NASA POWER in this sandbox. The team must run `scripts/fetch_weather.py` on a machine with internet access and present the weather provenance.

The material values remain library inputs with their source fields. No new external material-source audit was performed during this repair cycle.

The comfort band remains 15 to 28 C. It is a project placeholder and not a cited standard. The team must agree the band before presentation.

The 70/30 split of transmitted solar energy, ground properties, wind-scaling exponent, glazing starting values and other defaults remain documented assumptions unless replaced by sourced project inputs.

The pvlib comparison has been executed by the team in a clean environment. The sandbox here cannot reproduce it because pvlib is not installed.

The exported ANSYS Level-A wall-panel case was run in ANSYS Student 2026 R1. The comparison used 4021 Python points and reported a maximum absolute difference of 2.218076 C and RMS difference of 1.437016 C. The macro now builds the exact exported wall-layer stack with SOLID278, reads time-dependent outside and inside air tables, solves a transient thermal wall panel, and writes an inner-surface temperature CSV. The Python side exports the matching wall-main inner-surface series for comparison. The ANSYS Level-A wall-panel run has been completed in ANSYS Student 2026 R1.

The solver has not been validated against measured shelter sensor data.

## 8. Remaining problems by severity

### High

None identified in the implemented review-fix tests. ANSYS execution and real-weather retrieval remain team-side tasks rather than solved claims.

### Medium

The 1000-design/60 s screening target remains unmet. The prior repository measurement was 0.3629 designs/s on a two-design probe. The team later reported a 4-day solver run of about 1.9 s after vectorising the pvlib call path, but this sandbox did not reproduce the clean-environment benchmark.

A fresh dependency install from `requirements.txt` could not be completed because the sandbox has no package-index network access.

The current sandbox cannot reproduce the full-year pvlib comparison because pvlib is unavailable here. The team completed that comparison in its clean environment.

The prior reviewed build had 22 collected tests and was reported by the team as 22/22 passing in a clean environment. This sandbox previously stalled on a single-process solver run and cannot install pvlib. After the final integration patch, the repository contains 28 tests. The full final-suite run exceeded the sandbox execution window; the targeted integration set passed.

### Low

The screenshot harness must use its local embedded mode in this sandbox because loopback navigation is blocked.

## 9. What the team must do next

Run `scripts/fetch_weather.py` and place the resulting real Leh file in `data/weather`.

Run the exported Level A wall-panel case in the available ANSYS installation, export its results, and run `scripts/compare_ansys.py`. Put the actual difference on the presentation slide.

Agree and state the comfort band.

On the team machine, keep the clean Python 3.11+ environment as the release verification environment, install `requirements.txt`, and rerun the full pytest command after this latest baseline-selection patch. The team has already run the pvlib comparison in that clean environment.

Use the measured screening speed and the documented unresolved items in the presentation. Do not replace them with unverified accuracy, savings, cost or payback claims.

## 10. Web dashboard repair after live Windows check

The first live dashboard page appeared blank because the web initialization called `/api/default` against the complete annual weather file at the solver's 10-minute resolution before populating the form controls. On the review machine this made the page look unresponsive while the server performed a very large calculation. The web layer was changed to use a selected 14, 30 or 365 day weather window, to populate material and glazing controls before the default run, and to show an explicit computing status. Interactive dashboard runs now use hourly solver steps, which matches the hourly output contract while keeping the browser responsive.

The weather period selector is now sent to every interactive run, comparison and ANSYS export. The dashboard also supports selecting a user CSV as the active weather source. The default page loads a 14-day Leh window when `data/weather/leh_2024_hourly.csv` is present.

A live API smoke check in this build took 2.49 s for the 14-day default case in the sandbox. The dedicated web API tests report 3 passed. The slop scan still passes and `web/app.js` passes a JavaScript syntax check.

The interactive design comparison was reduced to the named baseline plus six seeded candidates so that the browser can complete a comparison in a practical time. This does not change the formal two-stage optimiser implementation or its documented 1000-design screening target.

### Clean-install dependency correction

The team reproduced a clean virtual-environment collection failure after the latest package resolution selected Starlette 1.7.0. The failure was:

`RuntimeError: The starlette.testclient module requires the httpx2 package to be installed.`

This release adds and pins `httpx2==2.13.1` in `requirements.txt` and `pyproject.toml`, and pins the other top-level tested dependencies to the versions used in the clean Windows run. Current Starlette documentation identifies `httpx2` as the optional dependency required by `TestClient`. The app runtime itself does not depend on TestClient; this dependency is needed for the bundled API tests.
