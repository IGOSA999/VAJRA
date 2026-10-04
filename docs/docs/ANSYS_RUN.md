# VAJRA Level-A ANSYS cross-check

VAJRA can export a transient 1 m² wall-panel case from the active design. The package contains the wall macro, boundary tables, material values and the Python wall inner-surface reference series.

## Team-side run

Run `exports/ansys/wall_panel.mac` in ANSYS Student 2026 R1 with the working directory set to `exports/ansys`. The macro uses SOLID278, the exported layer stack and time-dependent convection tables, and writes `ansys_wall_results.csv`.

Run:

```text
python scripts/compare_ansys.py
```

The recorded reference run used a three-day warm-up and 4,021 Python comparison points. It produced:

```text
maximum absolute difference: 2.218076 C
RMS difference:              1.437016 C
```

These numbers describe the Level-A wall-panel cross-check only. They are not full-shelter validation and are not measured-data accuracy claims.
