# VAJRA final engineering report

## Verification state

- Python test suite: 33 passed, 1 skipped in the current review workspace.
- `scripts/slop_scan.py`: passed.
- JavaScript syntax check: passed.
- Python compile check: passed.
- Background job submit path returns immediately and `/api/health` remains responsive while the worker runs.
- ANSYS Student 2026 R1 wall-panel cross-check: 4,021 points compared, maximum absolute difference 2.218076 C, RMS difference 1.437016 C.

## Live-demo failure handling

The original Render deployment log did not contain the failed Run or Compare request, so the exact original server-side failure could not be proven from that log alone. The application now returns non-empty JSON errors, logs request wall and CPU time, gates initial loading on health, and runs interactive solver work in a separate process.

## Engineering limits

The solver still models the stated thermal scope only. It does not perform CFD airflow, moisture/condensation modelling, structural design, snow-load design, cost or payback analysis, fuel-efficiency claims, measured-data validation or full-shelter ANSYS validation.

The 1,000-design screening benchmark should be measured on the clean team environment before claiming that target as achieved. The interactive dashboard uses real solver calls and does not serve precomputed simulation output.
