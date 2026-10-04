# VAJRA development notes

The release evolved from the core transient thermal solver to weather ingestion, material and glazing libraries, deterministic design comparison, a responsive dashboard, ANSYS Level-A export, and the final deployment architecture.

The web layer now separates CPU-bound simulation from the web process with a single spawned worker. Run, design comparison and wall-material comparison are background jobs with real progress and cancellation controls. The dashboard waits for health before loading the rest of the application and reports non-empty server errors.

The solver was profiled and the time-step loop was vectorised around prepared weather arrays and cached solar calculations. The code does not replace live calculations with stored demo values.

The current engineering record includes the ANSYS wall-panel cross-check, the pvlib comparison previously run by the team, and the remaining benchmark and validation limits stated in the final report.
