# Lunar Horizon — NASA Space Apps submission brief

## Innovation

Lunar Horizon combines NASA/JPL observer ephemerides, lunar surface geometry, and an explainable machine-learning surrogate in one landing-site comparison workflow. A planner can compare Sun illumination and direct-to-Earth visibility across prototype sites, custom coordinates, and delayed start times, then inspect why the model ranked one scenario higher.

The model score is transparent: 60% predicted sunlight and 40% predicted Earth visibility. The top three model candidates are recomputed using the physical ephemeris source, then ordered by the same score using those physical results.

## Impact

The prototype makes time-dependent lunar polar constraints easier to explore for mission planners, educators, and the public. It connects site, time, illumination, and communication geometry in a view that can be inspected and exported. Its scope is research, education, and preliminary planning; it is not flight-certified software.

## Technical implementation

- **Ephemerides:** Apparent, airless topocentric Sun/Earth azimuth and elevation from NASA/JPL Horizons, using a geodetic observer on the Moon. Raw JSON and provenance are cached locally.
- **Optional local physics backend:** NAIF SPICE with DE440 planetary states and the DE440 lunar orientation PCK, transformed through the Moon mean-Earth frame. The supplied binary PCK and text frame kernel are documented separately.
- **Data:** 14,610 JPL Horizons rows for the 9 original prototype points plus an exact south-pole geometry reference, over one year at six-hour cadence. Labels are JPL ephemeris calculations, not spacecraft observations.
- **Machine learning:** Compact random-forest altitude and cyclic-azimuth regressors trained on Horizons outputs. Held-out calendar-day results: Sun altitude MAE 0.331°, RMSE 0.467°, R² 0.943; Earth altitude MAE 0.347°, RMSE 0.472°, R² 0.990. The test set contains 2,960 rows; the training set contains 11,650. Custom locations farther than 5° from a sampled point are not model-ranked.
- **Validation:** 24 direct 15-minute Horizons windows across five sites, seasonal dates, an exact-pole point, and visibility crossings were compared with six-hour cached interpolation. Maximum altitude interpolation errors were 0.000439° for the Sun and 0.002830° for Earth. The exact-pole annual Sun-altitude range was −1.585° to +1.557°. This is a same-source interpolation check, not independent validation of local SPICE.
- **Terrain:** Bundled regional LOLA-derived 5 m/pixel elevation GeoTIFFs are ray-traced into azimuth horizon masks. The app applies a profile only when a tile covers the complete recorded ray radius; the UI shows that radius and identifies the interpolated grid. Custom observer controls include tile-center sample presets, labeled as data locations rather than landing sites. Synthetic profiles remain illustrative and do not affect visibility. Source: [NASA GSFC PGDA high-resolution LOLA topography](https://pgda.gsfc.nasa.gov/products/78), [PDS LOLA GDR dataset DOI 10.17189/1520642](https://doi.org/10.17189/1520642).

## Two-to-three-minute demonstration

1. Start the FastAPI service in the approved Linux environment and the Vite frontend in Windows. Set the mission window to 2026-09-01 18:00 UTC, five days, and a 10-minute cadence.
2. Enable LOLA terrain for Shackleton Rim West, compute visibility, and show the Sun/Earth curves against the two azimuth-dependent terrain horizons. Point out the profile's 5 km range and download the CSV.
3. Open ML recommendations to review the saved model's score explanation and the physical re-ranking of the top candidates.
4. Compare two site/date windows side by side and show the metric deltas.
5. Run the seasonal heatmaps, then open the mission simulator. Start with the full Earth-to-Moon overview, switch among the camera modes, and scrub the single mission timeline to show phase timing and projected-versus-calculated surface telemetry.
6. Compare the 5 km profile with a site that uses a short profile or geometric horizon. Explain that the selected radius is the terrain extent included and synthetic graphics remain display-only.

## Limitations

Candidate point coordinates and elevations were retained from the starting prototype and are not surveyed landing locations. The bundled LOLA products are regional, interpolated 5 m/pixel grids; terrain masks are used only within their complete coverage radius, which is shown in the UI. The ML artifact only covers the collected date and coordinate range and serves as an interpolation aid. SPICE-to-Horizons local agreement could not be measured in the development runtime because Windows App Control blocked CSPICE; the runtime used JPL Horizons directly. The app models visibility geometry and omits link budgets, antenna pointing, landing slopes, hazard constraints, and spacecraft-specific limits.

## Team

- Team name: ____________________
- Members and contributions: ____________________
- Demo link or screenshots: ____________________
