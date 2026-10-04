# Three minute demo path

1. Start with `python run.py` and open `http://127.0.0.1:8000`.
2. Point out the weather source line. The sandbox build shows the bundled synthetic test series until a real Leh file is fetched.
3. Show the default geometry, wall layers, glazing, ventilation and comfort inputs.
4. Press Run. Point to indoor and ambient temperature, the comfort band, and the minimum temperature annotation.
5. Point to the shelter section. Explain that the drawing is generated from the current geometry and material layers.
6. Point to heat flow by element and the metric strip. State that heating energy is an ideal-heater model estimate.
7. Change insulation thickness and run again. Compare the model outputs.
8. Use the compare control to run the reduced candidate sweep and show the named baseline row.
9. Export the design sheet. Show that it carries inputs, metrics, weather provenance and the model-estimate note.
10. Export the ANSYS Level A case. Show the three generated files and state that the team must run the macro in the installed ANSYS version and return the result to `compare_ansys.py`.
