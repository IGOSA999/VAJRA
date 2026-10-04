# Web usability fix

The first page previously waited on a full-year 10-minute free-floating run and a full-year 10-minute heater run before populating the controls. That made the screen appear broken while `/api/default` was computing tens of thousands of time steps.

The web layer now uses the selected 14, 30 or 365 day window, populates all selectors before the default run, shows a live status message, wires the period selector to the API, supports uploaded CSV weather as the active source, and passes the selected window into the ANSYS export.

The solver itself is unchanged by this web fix. The 10-minute transient model remains available through the API and the test suite.

Interactive API runs now use hourly solver steps. This matches the dashboard output contract and keeps the browser responsive while the core 10-minute mode remains available for verification and detailed programmatic runs.
