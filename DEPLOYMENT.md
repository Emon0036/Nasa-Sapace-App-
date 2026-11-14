# Deployment and cloud SQL

## Hosting layout

- **Frontend:** Vercel, with the Vercel project root set to `frontend/`.
- **API:** Render, using the root `render.yaml` blueprint. The service is configured for Singapore, near Bangladesh and APAC users.
- **Database:** Neon Postgres in Singapore (`ap-southeast-1`). Keep it in the same region as the Render API service and use Neon's pooled connection string for `DATABASE_URL`.

The frontend calls `/api/...` on its own origin. `frontend/vercel.json` forwards those requests to the Render API, so the browser does not need a cross-origin API URL.

## Provisioning

1. Create a Neon Postgres project on the free plan and copy its pooled connection string.
2. In Render, create a Blueprint from this repository and set the secret `DATABASE_URL` on `lunar-horizon-api` to that connection string. Do not commit the connection string or put it in a Vite `VITE_*` variable.
3. In Vercel, import the GitHub repository and set the project root to `frontend/`. Keep the build command `npm run build` and output directory `dist`.
4. After the API is deployed, check `https://lunar-horizon-api.onrender.com/api/health` and `https://lunar-horizon-api.onrender.com/api/saved-missions/status`.

The Render build downloads the public LOLA tiles and DE440 lunar frame/orientation kernels, checking each size and SHA-256 before accepting them, and trains the ML artifact from the checked-in Horizons data. The saved-profile table is created from `backend/sql/001_saved_mission_profiles.sql` when the first SQL-backed profile request runs. Saved profiles contain the site and mission input parameters only. Opening one requires a new simulation request, so Sun/Earth telemetry is calculated by the existing science engine rather than loaded from a stale snapshot.

## Saved profile privacy

Saved profiles are anonymous and scoped to a browser-generated UUID. The API stores only a SHA-256 digest of that identifier. There is no account or cross-device sync; clearing the browser's local storage removes the key needed to find those profiles. The API retains at most 50 profiles for each browser key.

Without `DATABASE_URL`, the simulator and all scientific endpoints continue to work, and the mission library reports that cloud saves are unavailable.
