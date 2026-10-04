# Iteration log

## 2026-10-03

M0: built the weather fixture loader, single wall conduction path, indoor air node, API endpoint and plain dashboard. Evidence: end to end API run and T1.

M1: implemented transient layered conduction, exterior convection and radiation, solar input, glazing, ventilation, ground coupling and ideal heater run. Evidence: T1 to T6 and T10 pass on fixtures. PCM is not yet represented as a separate apparent-capacity mass node, so the M1 gate is recorded as partial.

M2: added NASA POWER request/parser, user CSV validation, bundled-data path and a sourced material/glazing library. Evidence: T9 and source-column checks pass. NASA download itself was not run in the sandbox because outbound network access was unavailable.

M3: added metrics, baseline comparison and a seeded parameter sweep. Evidence: T7 and T8 pass on reduced fixtures. The 1000-design speed target was not met in the sandbox, so the shortfall is recorded rather than hidden.

M4: built the working dashboard, actual-input shelter section SVG, heat-flow chart, comparison table, empty/loading/error states and 390 px stacking. Evidence: `scripts/slop_scan.py` passes and screenshots were rendered at 1440 by 900 and 390 by 844. The screenshot harness used the real API payload embedded into the page because loopback navigation is blocked by the sandbox browser policy.

M5: added the Level A ANSYS export and comparison scripts. Evidence: export files are generated and structurally checked. ANSYS itself was not available to the sandbox and must be run by the team.

M6: added the README, demo path and final status report. A clean Windows virtual environment install was not executed because external package download was unavailable in the sandbox.

## 2026-10-03 independent review reproduction

Before fixes, a targeted review test file was run. Eight assertions failed and the optional pvlib test was skipped because pvlib was not installed.

1. Clean install metadata defect: `python-multipart` was absent from requirements.txt. A fresh virtual environment could not install dependencies in this offline sandbox, and the clean environment then could not import FastAPI.
2. A 500 kg water design produced exactly the same 30-minute temperature series as the no-mass design. PCM with 200 kJ/kg also produced the same minimum temperature as the zero-latent case. This reproduced the ignored-interior-mass defect.
3. `_candidate(base, 1)` started the wall with stone rather than mineral wool, reproducing the inside-insulation ordering defect.
4. The first 24 candidates all used `stone_masonry`, reproducing the diagonal sweep and missing-material-comparison defect.
5. The four required WOFF2 files were absent from `web/fonts`, reproducing the font packaging defect.
6. The independent boundary bookkeeping check reported a 1.5963% maximum closure ratio for the heater run on the four-day fixture, above the 0.5% criterion.
7. pvlib was unavailable, so the requested cross-check had no executable comparison path in the original build.
8. The final report stated that 10 tests passed while the actual pytest suite reported 11.

The failing output is preserved in `/tmp/review_repro.out` in the build workspace; the durable record above states the observed values.

## 2026-10-03 review fixes

1. Install metadata: added `python-multipart>=0.0.20` to requirements.txt and pyproject.toml. A fresh virtual environment was created, but installation from requirements.txt failed because the sandbox has no external package access (`Temporary failure in name resolution`), so a clean dependency install remains unverified here.

2. Interior mass and PCM: the solver now reads `interior_mass`, couples the mass node to indoor air through `h_inside_w_m2k * surface_area_m2`, uses water as sensible storage, and uses the apparent heat capacity expression for paraffin PCM with iteration to 0.01 K. Design validation rejects unsupported keys and missing PCM fields. Regression tests pass. On the seven-day synthetic fixture, no-mass versus 500 kg water daily swing was 3.1236 K versus 3.0551 K. The PCM minimum rose from -10.7396 C to -10.7172 C for 200 kJ/kg latent heat, with a maximum boundary closure ratio of 6.11e-15 and two apparent-capacity iterations.

3. Insulation order: the sweep now writes insulation first because construction layers are outside to inside. On the seven-day synthetic fixture, outside insulation gave a 5.3589 K daily swing and inside insulation gave 9.9180 K.

4. Sweep: wall material is now sampled across stone_masonry, concrete_dense, fired_clay_brick, rammed_earth, adobe and timber, each with 0, 50, 100 and 150 mm mineral wool options. The first 24 seeded candidates cover all 24 material/insulation combinations. Same-seed rankings are identical. Material-only comparison produces distinct heating estimates: stone 109.543 kWh, dense concrete 108.187 kWh, fired clay brick 103.428 kWh, rammed earth 104.953 kWh, adobe 101.467 kWh, timber 79.867 kWh on the seven-day synthetic fixture with 100 mm outside insulation. A 24-candidate stage-1 timing probe on 20 synthetic days was not completed within the sandbox budget; a two-design screening measurement took 5.5116 s for 0.3629 designs/s, so the 1000-design/60 s target is not met.

5. Fonts: bundled four WOFF2 files and OFL text under web/fonts. `slop_scan.py` now checks the files and CSS declarations. Screenshot harness reports IBM Plex Sans, IBM Plex Mono and Source Serif 4 loaded at both 1440x900 and 390x844. The scan passes.

6. Energy balance: the original independent boundary bookkeeping check was 1.5963% on the four-day heater fixture. After making the soil boundary part of the same implicit domain and using the independent boundary-flow residual as T2, the same fixture is 6.11e-15 ratio. The equation-level residual is also below 1e-9. The independent criterion is the reported T2 criterion.

7. pvlib: the conditional full-year comparison test is present. pvlib is not installed in this sandbox, so the test is skipped rather than substituted with a hand-waved result.

8. Reporting: `tests/test_fix_prompt.py` reports 10 passed and 1 skipped. The original T1 to T11 files each report one pass, for 11 passed. The complete collected suite is therefore 22 tests: 21 passed and 1 skipped when run file-isolated. A single-process `pytest -q -rs` run was also attempted and repeatedly stalled at T3 in this sandbox after the review-fix tests; the file-isolated result is recorded rather than calling the stalled command a pass.

The dashboard screenshots were regenerated after the font change. The sandbox browser blocks direct loopback navigation, so the screenshot harness embeds the same bundled font bytes and real API payloads into the page before rendering. This verifies the visual state without claiming that the blocked browser navigation succeeded.
## 2026-10-03 post-v3 corrective review

The stage-2 finalist selection was reviewed after v3. Reproduction before the patch: when the baseline sorted below the first 21 screening candidates, `screening[:21]` omitted the baseline from the full-period confirmation. A direct reproduction with the baseline at rank 26 printed `pre-fix baseline included: False`.

The selection was changed to keep the named baseline plus the best 20 non-baseline screening candidates. A targeted integration smoke test using the real `optimise_two_stage` function with a mocked solver confirmed 21 confirmation rows: 1 baseline and 20 non-baseline candidates. The regression test `test_fix_04_stage_2_always_keeps_baseline` passed.

`python -m compileall -q vajra tests` passed. `python scripts/slop_scan.py` passed. The full current suite was not rerun in this sandbox because the earlier single-process run stalled in the solver and pvlib is unavailable.



## 2026-10-03 live dashboard usability repair

Observed live Windows behavior: the page displayed the layout but kept `Weather: loading`, with empty plots and controls not yet populated. Cause: page initialization waited for `/api/default`, which ran the complete 2024 weather file through two 10-minute simulations before JavaScript populated the selectors.

Fix: added explicit weather windows, made the period selector effective, populated selectors before the default run, added a status line, added CSV upload activation, and changed interactive web simulations to hourly steps. The default 14-day API case completed in 2.49 s in the repair workspace. Targeted web API tests: 3 passed. `scripts/slop_scan.py`: passed. Node syntax check: passed.

The live comparison endpoint was also timed. The original 25-row comparison was too slow for an interactive page, so the dashboard endpoint now uses the baseline plus six seeded candidates. The formal `optimise_two_stage` 1000-design workflow is unchanged.
