# Lunar Horizon — South Pole Mission Planning Tool

An interactive comparison tool for evaluating **solar power** and **direct-to-Earth communication**
conditions at candidate lunar south polar landing sites.

Given a site, a date, and a horizon mask, it computes and visualizes:

- **Sun altitude / azimuth** over time → continuous power, shadow periods
- **Earth altitude / azimuth** over time → direct comm windows (with libration wobble)
- **Comparison grid** of multiple sites at a glance
- **Date sweep heatmap** showing seasonal sunlight & Earth visibility variation

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Windows: use the environment's Python directly so the command cannot pick up
# a stale Streamlit launcher from another folder.
.venv\\Scripts\\python.exe -m streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).

## How accurate is it?

- **With compatible SPICE kernels** (`de440s.bsp`, `naif0012.tls`, `pck00011.tpc`, and the
  lunar binary PCK/frame files placed in `kernels/`) the ephemeris uses the JPL SPICE backend.
- **Without kernels** the app uses an analytic model (low-precision series for Sun/Earth + Meeus
  lunar orientation). This is accurate to a few tenths of a degree for Sun/Earth directions — more
  than sufficient for visibility comparisons near the pole.
- **Horizon mask**: this repository currently falls back to synthetic ridge profiles because
  `data/horizons/` contains no site-specific profiles. Add real LOLA-derived JSON profiles or a
  GeoTIFF-generated profile before treating visibility percentages as site-survey data.

## Project layout

```
project/
├── kernels/              # Optional: SPICE files (see below)
├── dem/                  # Optional: LOLA GeoTIFFs
├── data/
│   └── horizons/         # Precomputed horizon profiles per site
├── src/
│   ├── ephemeris.py      # Sun & Earth positions (SPICE + analytic fallback)
│   ├── horizon.py        # Horizon profile generator
│   ├── sites.py          # Candidate landing sites
│   ├── analysis.py       # Site/date evaluation
│   ├── plotting.py       # Sky plots, elevation plots, heatmaps
│   └── app_helpers.py    # Streamlit glue
├── app.py                # Streamlit entrypoint
└── requirements.txt
```

## Adding SPICE kernels (optional, for full accuracy)

Download from NAIF:

- `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp`
- `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls`
- `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc`
- `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc`
- (optional) `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf`

Drop them into `kernels/`. The app auto-detects them on startup.

## Adding a real DEM (optional)

Drop a LOLA polar GeoTIFF into `dem/` (e.g. `LDEM_80S_20M.tif`), then from a Python session:

```python
from src.horizon import build_horizon_profile
profile = build_horizon_profile(
    site_lat=-89.5, site_lon=0, site_elev=0,
    dem_path="dem/LDEM_80S_20M.tif",
    max_range_km=30.0,
)
profile.save("data/horizons/my_site.json")
```

## Sites included

Artemis III candidate regions, plus reference sites:

- Shackleton-Henson Connecting Ridge
- Shackleton Rim (East / West / North)
- de la Rue
- Leibnitz Beta
- Cabeus (LCROSS impact reference)
- Peary (north pole reference)
- A generic flat-site reference

## License

MIT.
