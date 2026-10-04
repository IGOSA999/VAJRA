# VAJRA Level A ANSYS run

The dashboard prepares the files in `exports/ansys` for the selected design and weather window.

Files used by the APDL macro:

- `wall_panel.mac`
- `boundary_conditions_table.txt`
- `boundary_conditions_table_inside.txt`

Supporting files:

- `boundary_conditions.csv`
- `materials.csv`
- `python_wall_results.csv`

Open ANSYS Mechanical APDL with the working directory set to `exports/ansys`. Read or execute
`wall_panel.mac`. The macro uses SOLID278 and a one square metre wall panel with the exact wall
layer order exported by VAJRA. It applies time-varying outside and inside air temperatures as
convection bulk temperatures from the tabulated files.

After the solve, the macro writes `ansys_wall_results.csv`. The compare script then reports the
maximum and RMS difference between the Python wall inner-surface temperature series and the ANSYS
series:

```text
python scripts/compare_ansys.py
```

The macro has not been run by VAJRA here. Confirm the commands against the installed ANSYS release
before using the output as a validation result. Current ANSYS documentation identifies SOLID278
as a 3-D 8-node thermal solid and documents tabular time-dependent convection inputs via `SF`
and `*DIM`/`*TREAD` tables. See the official ANSYS documentation for the installed release.
