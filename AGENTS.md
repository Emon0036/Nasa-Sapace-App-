# Lunar Horizon project guidance

- The frontend is React + Vite + TypeScript in `frontend/`; the HTTP API is FastAPI in `backend/`.
- Existing Python modules in `src/` are the source of truth for ephemerides, horizon masks, visibility summaries, simulation telemetry, and recommendation logic. Do not recreate scientific calculations in JavaScript.
- Preserve UTC timestamps, east-positive lunar longitude, and the units already used by the scientific modules. Validate API inputs and keep JSON response shapes stable.
- Distinguish geometric, terrain-adjusted, and synthetic horizon results. Never label a synthetic profile as LOLA data or a Horizons calculation as a spacecraft observation.
- Keep ML predictions visibly separate from physical results. Use the saved model schema, provenance, and held-out metrics; physically verify recommendations when the ephemeris backend is available.
- Treat mission launch, transit, orbit, and descent artwork as illustrative unless backed by computed trajectory data. Surface Sun/Earth telemetry must come from `src/sim.py` and the existing ephemeris engine.
- Preserve working functionality and prefer small, typed modules with explicit errors over duplicate calculations or hidden fallbacks.
- After API changes, run the backend tests and scientific regression tests. After frontend changes, run the TypeScript check and Vite production build. Report anything the environment prevents you from verifying.
