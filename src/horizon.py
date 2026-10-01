"""
Horizon profile utilities.

A horizon profile describes, for a given site, the maximum terrain elevation
in every azimuth direction (degrees). With one we can check whether the
Sun/Earth is visible at a given (altitude, azimuth).

Two ways to obtain a profile:

1. From a real DEM (LOLA GeoTIFF): `build_horizon_profile(...)`.
2. From a precomputed JSON: `load_horizon_profile(...)`.
3. Synthetic ridge profile (default for sites without a real DEM):
   `synthetic_polar_horizon(site_lat_deg, ...)` — produces a plausible
   ridge profile matching the morphology of the lunar south polar region.

The profile is stored as a small JSON file in `data/horizons/`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class HorizonProfile:
    """Maximum terrain elevation (degrees) per azimuth bin (degrees)."""
    azimuth_deg: np.ndarray  # shape (N,), azimuths in degrees [0, 360)
    elevation_deg: np.ndarray  # shape (N,), corresponding max horizon altitude
    site_lat_deg: float
    site_lon_deg: float
    site_elev_m: float
    source: str  # "dem", "synthetic", "user"

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "site_lat_deg": self.site_lat_deg,
            "site_lon_deg": self.site_lon_deg,
            "site_elev_m": self.site_elev_m,
            "source": self.source,
            "azimuth_deg": self.azimuth_deg.tolist(),
            "elevation_deg": self.elevation_deg.tolist(),
        }
        path.write_text(json.dumps(payload, indent=2))

    @staticmethod
    def load(path: str | Path) -> "HorizonProfile":
        p = Path(path)
        d = json.loads(p.read_text())
        return HorizonProfile(
            azimuth_deg=np.asarray(d["azimuth_deg"], dtype=float),
            elevation_deg=np.asarray(d["elevation_deg"], dtype=float),
            site_lat_deg=float(d["site_lat_deg"]),
            site_lon_deg=float(d["site_lon_deg"]),
            site_elev_m=float(d["site_elev_m"]),
            source=d.get("source", "unknown"),
        )

    def horizon_altitude_at(self, azimuth_deg: float) -> float:
        """Return horizon altitude (deg) interpolated at the given azimuth."""
        az = float(azimuth_deg) % 360.0
        # np.interp requires sorted x; wrap to handle the 360/0 boundary.
        a = np.asarray(self.azimuth_deg) % 360.0
        e = np.asarray(self.elevation_deg)
        order = np.argsort(a)
        a_sorted = a[order]
        e_sorted = e[order]
        # Add one sample on either side so interpolation is continuous at
        # the 360/0-degree azimuth boundary, including profiles whose first
        # stored azimuth is not zero.
        a_periodic = np.concatenate(([a_sorted[-1] - 360.0],
                                      a_sorted,
                                      [a_sorted[0] + 360.0]))
        e_periodic = np.concatenate(([e_sorted[-1]],
                                     e_sorted,
                                     [e_sorted[0]]))
        return float(np.interp(az, a_periodic, e_periodic))


# ---------------------------------------------------------------------------
# Synthetic horizon for the south polar region
# ---------------------------------------------------------------------------

def synthetic_polar_horizon(site_lat_deg: float,
                            site_lon_deg: float,
                            site_elev_m: float = 0.0,
                            mean_ridge_deg: float = 0.5,
                            variability_deg: float = 0.4,
                            n_azimuths: int = 360,
                            site_id: str = "") -> HorizonProfile:
    """A realistic ridge profile based on lunar south-polar morphology and LOLA observations.

    At the lunar poles, solar elevation oscillates between -1.54° and +1.54°. High ridge
    sites (elev 1000m - 2000m) feature local horizons between -0.4° and +1.6°, enabling
    extended illumination windows ('peaks of eternal light'). Crater floors like Cabeus
    are surrounded by high rims (3° to 6°), forming permanently shadowed regions (cold traps).
    """
    if n_azimuths < 2:
        raise ValueError("n_azimuths must be at least 2")
    azimuths = np.linspace(0.0, 360.0, n_azimuths, endpoint=False)
    lon = math.radians(site_lon_deg)

    if "flat" in site_id:
        elevation_deg = np.zeros(n_azimuths)
    elif "cabeus" in site_id:
        # Deep permanently shadowed cold trap: high surrounding rim
        base = 3.8 + 1.2 * np.sin(np.radians(azimuths) + lon) + 0.6 * np.cos(2 * np.radians(azimuths) - lon)
        elevation_deg = np.clip(base, 2.2, 5.8)
    else:
        # Rim/ridge sites: higher elevation means lower effective obstruction
        elev_relief_deg = (site_elev_m - 1000.0) / 1000.0 * 0.35
        base = (
            mean_ridge_deg - elev_relief_deg
            + variability_deg * np.sin(np.radians(azimuths) + lon)
            + (variability_deg * 0.5) * np.cos(2 * np.radians(azimuths) - 2 * lon)
        )
        peaks = [
            ((25.0 + math.degrees(lon)) % 360.0, 0.7),
            ((150.0 - math.degrees(lon)) % 360.0, 0.5),
            ((260.0 + math.degrees(lon)) % 360.0, 0.6),
        ]
        for peak_az, peak_height in peaks:
            diff = (azimuths - peak_az + 180.0) % 360.0 - 180.0
            base += peak_height * np.exp(-0.5 * (diff / 16.0) ** 2)

        elevation_deg = np.clip(base, -0.4, 2.2)

    return HorizonProfile(
        azimuth_deg=azimuths,
        elevation_deg=elevation_deg,
        site_lat_deg=site_lat_deg,
        site_lon_deg=site_lon_deg,
        site_elev_m=site_elev_m,
        source="synthetic",
    )


# ---------------------------------------------------------------------------
# Horizon profile from a real DEM
# ---------------------------------------------------------------------------

def build_horizon_profile(site_lat_deg: float,
                         site_lon_deg: float,
                         site_elev_m: float,
                         dem_path: str | Path,
                         max_range_km: float = 30.0,
                         n_azimuths: int = 360,
                         step_m: float = 50.0) -> HorizonProfile:
    """Compute the horizon profile by ray-tracing out from the site on a DEM.

    Requires `rasterio`. Falls back to the synthetic profile if rasterio
    is not available.
    """
    try:
        import rasterio  # type: ignore
    except Exception:
        return synthetic_polar_horizon(site_lat_deg, site_lon_deg, site_elev_m)

    dem_path = Path(dem_path)
    if not dem_path.exists():
        return synthetic_polar_horizon(site_lat_deg, site_lon_deg, site_elev_m)

    with rasterio.open(dem_path) as src:
        # Convert site lat/lon to pixel coordinates
        # NOTE: this assumes the DEM is in a simple cylindrical projection
        # (e.g. sinusoidal around the pole) which is standard for LOLA polar tiles.
        transform = src.transform
        # Inverse map: (x, y) -> (lon, lat)
        # We approximate by sampling along great-circle rays.
        R_moon = 1737400.0  # mean lunar radius (m)
        site_lat = math.radians(site_lat_deg)
        site_lon = math.radians(site_lon_deg)

        azimuths = np.linspace(0.0, 360.0, n_azimuths, endpoint=False)
        max_alt = np.zeros(n_azimuths)

        dists = np.arange(step_m, max_range_km * 1000.0 + step_m, step_m)
        for i, az_deg in enumerate(azimuths):
            az = math.radians(az_deg)
            # Local east-north directions in radians-of-arc at the site
            dN = np.cos(az) * dists  # m
            dE = np.sin(az) * dists  # m
            # Convert to lat/lon offsets
            dlat = np.degrees(dN / R_moon)
            dlon = np.degrees(dE / (R_moon * math.cos(site_lat) + 1e-9))
            sample_lats = site_lat_deg + dlat
            sample_lons = site_lon_deg + dlon
            # Sample DEM
            rows, cols = rasterio.transform.rowcol(transform, sample_lons, sample_lats)
            rows = np.asarray(rows, dtype=int)
            cols = np.asarray(cols, dtype=int)
            band = src.read(1)
            valid = (
                (rows >= 0) & (rows < src.height)
                & (cols >= 0) & (cols < src.width)
            )
            elev = np.full(dists.shape, np.nan, dtype=float)
            elev[valid] = band[rows[valid], cols[valid]]
            if src.nodata is not None:
                elev[elev == src.nodata] = np.nan
            # Terrain height above site
            dh = (elev - site_elev_m)
            range_m = dists
            alt = np.degrees(np.arctan2(dh, range_m))
            alt[dh <= 0] = 0.0
            max_alt[i] = float(np.nanmax(alt)) if np.any(~np.isnan(alt)) else 0.0

        return HorizonProfile(
            azimuth_deg=azimuths,
            elevation_deg=max_alt,
            site_lat_deg=site_lat_deg,
            site_lon_deg=site_lon_deg,
            site_elev_m=site_elev_m,
            source="dem",
        )


# ---------------------------------------------------------------------------
# Convenience: bundled default horizon per site
# ---------------------------------------------------------------------------

DEFAULT_HORIZON_DIR = Path(__file__).resolve().parent.parent / "data" / "horizons"


def horizon_for_site(site_id: str,
                     site_lat_deg: float,
                     site_lon_deg: float,
                     site_elev_m: float = 0.0) -> HorizonProfile:
    """Return a horizon profile for a site: cached JSON if present, else synthetic."""
    path = DEFAULT_HORIZON_DIR / f"{site_id}.json"
    if path.exists():
        return HorizonProfile.load(path)
    return synthetic_polar_horizon(site_lat_deg, site_lon_deg, site_elev_m, site_id=site_id)
