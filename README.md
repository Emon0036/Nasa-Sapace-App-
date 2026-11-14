# Lunar Horizon

Lunar Horizon is a research and education prototype for planning lunar south-pole observation windows. The application compares apparent Sun illumination, direct-to-Earth visibility, simultaneous operating windows, and seasonal changes using the existing Python scientific engine.

It is not flight-certified mission software. Candidate points and elevations are nominal prototype inputs, not surveyed landing sites.

## Architecture

- **React + Vite + TypeScript** provide the responsive mission-control interface in `frontend/`.
- **FastAPI** provides validated JSON endpoints in `backend/main.py`.
- **Scientific source of truth:** `src/ephemeris.py`, `src/horizons.py`, `src/horizon.py`, `src/analysis.py`, `src/sim.py`, and `src/sites.py`.
- **ML and ranking:** `src/recommender.py` and `ml/`; recommendations are estimates and the top candidates are checked with the physical ephemeris engine when it is available.
- **Mission simulation:** React drives a single authoritative mission clock and a Three.js viewport. The scene's phases, UTC time, spacecraft position, playback, timeline, and telemetry panel stay synchronized with the FastAPI mission-plan response.
- The mission-plan response still includes the legacy `simulator_html` field to keep its JSON shape stable. The React interface renders the returned phase and surface-telemetry data directly rather than displaying that iframe.
- The retained `app.py` is a legacy Streamlit interface only. FastAPI does not import Streamlit. To run the old interface, install `requirements-legacy.txt` separately.

## Current scientific inputs and limitations

- An approved Linux backend tries NAIF SPICE with the bundled kernels when they load successfully; otherwise it queries apparent, airless topocentric azimuth/elevation from NASA/JPL Horizons. On Windows it skips CSPICE and uses Horizons; it does not attempt to bypass Application Control. Query errors are reported; there is no analytic angle fallback.
- The processed dataset contains 14,610 Horizons-derived samples from 2026-06-01 through 2027-06-01. They are calculations, not spacecraft observations.
- NASA GSFC PGDA LRO-LOLA 5 m/pixel regional elevation tiles are downloaded from their official URLs and checksum-verified for deployment. Terrain profiles are used only where a tile completely covers the recorded ray radius; other locations use geometric visibility. The elevation grids are interpolated, and the UI shows each profile's source and range.
- The custom observer controls include georeferenced tile-center presets to make the bundled LOLA coverage easy to explore. These are DEM sample locations, not surveyed landing sites.
- ML ranking is limited to the trained model's date and sampled-coordinate coverage. Physical verification remains authoritative.
- The React mission overview shows the complete Earth-to-Moon path, with selectable follow, launch, orbit, descent, surface, and sky-radar views. The spacecraft animation and route are illustrative and explicitly marked not to scale; they are not a validated flight trajectory.
- One React mission clock drives playback, phase progress, UTC, spacecraft position, and telemetry selection. Surface Sun/Earth values come from `src/sim.py` and the configured ephemeris engine; before landing, the sidebar labels them as projected landing-site conditions.
- Mission imagery uses the bundled NASA/GSFC Blue Marble Earth map and NASA LRO/LROC lunar color map. These are rendering textures only; horizon masks and physical visibility still come from the science engine. Credits and source links are in `frontend/public/textures/README.md`.

## Local development

### One-command Windows start

After the Python environment and frontend packages are installed, run this once
from the project root:

```powershell
.\start-local.cmd
```

The script checks the API health endpoint, starts FastAPI in a separate visible
window when needed, then runs Vite in the current terminal. Keep both open
while using the app. If you start the API manually, run the frontend commands
below in a second terminal.

### React frontend on Windows

Install Node.js 20 or later, then from PowerShell:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`). With the default empty `VITE_API_BASE_URL`, Vite proxies `/api` to `http://localhost:8000`.

### FastAPI backend in an approved Linux environment

The backend can run in WSL2 if permitted, Codespaces, a Linux VM, or a Linux host. Use Python 3.12 to match the saved model's scikit-learn 1.6.1 serialization version:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Generated LOLA horizon JSON profiles are included. To rebuild them from the
bundled GeoTIFFs, install `requirements.txt` and run
`python data_pipeline/build_lola_horizons.py` from the repository root.

The API documentation is at `http://localhost:8000/docs`. Do not bypass Windows Application Control restrictions. For a Linux backend on a different host, set `VITE_API_BASE_URL` in `frontend/.env.local` to that API origin and set `CORS_ORIGINS` for the exact frontend origin on the backend.

### Environment configuration

- Copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` only when the API is not reachable through the local Vite proxy.
- Copy `backend/.env.example` to `backend/.env` and set `CORS_ORIGINS` to comma-separated local and production frontend origins. The API loads that file locally; production hosts should set the variable in their environment and use explicit origins.
- No NASA credentials are required. Horizons queries need outbound network access when the requested time window is not in the local raw-response cache.

## API endpoints

- `GET /api/health` — service status and selected ephemeris backend.
- `GET /api/sites` — nominal site catalogue and configured horizon source.
- `GET /api/terrain/regions` — georeferenced center presets for the bundled PGDA LOLA tiles.
- `GET /api/science/status` — SPICE, terrain, dataset, ML availability, and limitations.
- `POST /api/analyze` — site ephemeris time series and visibility summaries.
- `POST /api/golden-windows` — sampled intervals with both Sun and Earth visible.
- `POST /api/compare` — independently calculated scenarios and metric deltas.
- `POST /api/seasonal-sweep` — existing date sweep across selected sites.
- `POST /api/simulation/plan` — mission phases and actual surface sky telemetry.
- `GET /api/ml/metrics`, `POST /api/ml/predict`, `POST /api/recommend` — saved evaluation, model ranking, and physically checked shortlist.

All timestamps are serialized in ISO 8601. Date/time fields entered in the browser are converted to UTC before requests. Analysis sampling is validated to 5,000 points; the simulation surface series is limited to 3,000 points.

## Tests and production build

Install the additional API test dependency, then run the scientific and API tests:

```bash
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Build and type-check the frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

The API tests mock ephemeris calculations to remain deterministic and offline. The existing scientific regression tests exercise geometry, data parsing, horizon interpolation, and summary calculations.

## Deployment preparation

- See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the Vercel frontend, Render API, Neon Postgres setup, and runtime environment variables.
- Render builds install the pinned science dependencies, fetch and checksum-verify the public NAIF lunar orientation kernel and NASA LOLA source tiles, then train the ML artifact from the checked-in Horizons dataset.
- Vercel forwards same-origin `/api/...` requests to the Render API; no public database URL or SQL credentials go into the frontend build.

## Data and model provenance

- Dataset source and collection details: `data/processed/horizons_ephemeris.provenance.json`.
- LOLA source tiles, citations, checksums, and generated profile coverage: `data/terrain/lola/README.md` and `data/terrain/lola/provenance.json`.
- Saved held-out metrics: `ml/metrics.json`.
- Model artifact: `ml/models/lunar_conditions_rf.joblib`.
- Kernel URLs, types, and hashes: `kernels/README.md`.
- Existing scientific validation report: `data/processed/ephemeris_validation.json`.

The saved model is an interpolation surrogate, not a forecast or replacement for Horizons/SPICE. Its recommendation score uses the documented 60% sunlight and 40% Earth-visibility weighting. Synthetic terrain is excluded from model scoring.

## Demo walkthrough

1. Start FastAPI in the approved Linux environment and start the Vite frontend on Windows.
2. Select **Shackleton Rim (West)**, enable **Use LOLA terrain where covered**, choose a mission window, and compute visibility. Its 5 km horizon profile demonstrates the terrain mask.
3. Open **Site analysis** to inspect Sun/Earth time series against the azimuth-dependent LOLA thresholds, review the profile radius/source, inspect sampled joint windows, and export the CSV.
4. Open **Scenario compare** to calculate side-by-side site/date windows.
5. Run **Seasonal sweep** and inspect the date-by-site heatmap.
6. Build a **Mission simulator** plan; start in Mission Overview, switch camera modes, scrub the unified timeline, and check the projected landing-site readings against calculated surface telemetry.
7. If the saved model is available, run **ML recommendations** and compare estimates with the physical top-three verification.
8. Call out the coordinate, terrain, model coverage, and flight-certification limitations during the demonstration.
