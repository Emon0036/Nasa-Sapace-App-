"""
Horizon profile utilities.

A horizon profile describes, for a given site, the maximum terrain elevation
in every azimuth direction (degrees). With one we can check whether the
Sun/Earth is visible at a given (altitude, azimuth).

Two ways to obtain a profile:

1. From a correctly referenced lunar DEM (for example a LOLA GeoTIFF): `build_horizon_profile(...)`.
2. From a precomputed JSON: `load_horizon_profile(...)`.
3. Synthetic ridge profile (default for sites without a real DEM):
   `synthetic_polar_horizon(site_lat_deg, ...)` — illustrative only; it is
   not a measured LOLA terrain profile.

The profile is stored as a small JSON file in `data/horizons/`.
"""

from __future__ import annotations

import json
import hashlib
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
    coverage_range_km: float | None = None
    source_detail: str | None = None
    source_url: str | None = None
    resolution_m: float | None = None

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "site_lat_deg": self.site_lat_deg,
            "site_lon_deg": self.site_lon_deg,
            "site_elev_m": self.site_elev_m,
            "source": self.source,
            "coverage_range_km": self.coverage_range_km,
            "source_detail": self.source_detail,
            "source_url": self.source_url,
            "resolution_m": self.resolution_m,
            "azimuth_deg": self.azimuth_deg.tolist(),
            "elevation_deg": self.elevation_deg.tolist(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def load(path: str | Path) -> "HorizonProfile":
        p = Path(path)
        d = json.loads(p.read_text(encoding="utf-8"))
        azimuth = np.asarray(d["azimuth_deg"], dtype=float)
        elevation = np.asarray(d["elevation_deg"], dtype=float)
        if azimuth.ndim != 1 or elevation.ndim != 1 or len(azimuth) != len(elevation) or len(azimuth) < 2:
            raise ValueError(f"Invalid horizon profile arrays in {p}")
        if not np.isfinite(azimuth).all() or not np.isfinite(elevation).all():
            raise ValueError(f"Non-finite horizon profile values in {p}")
        return HorizonProfile(
            azimuth_deg=azimuth,
            elevation_deg=elevation,
            site_lat_deg=float(d["site_lat_deg"]),
            site_lon_deg=float(d["site_lon_deg"]),
            site_elev_m=float(d["site_elev_m"]),
            source=d.get("source", "unknown"),
            coverage_range_km=(float(d["coverage_range_km"]) if d.get("coverage_range_km") is not None else None),
            source_detail=d.get("source_detail"),
            source_url=d.get("source_url"),
            resolution_m=(float(d["resolution_m"]) if d.get("resolution_m") is not None else None),
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
        x = np.concatenate(([a_sorted[-1] - 360.0], a_sorted, [a_sorted[0] + 360.0]))
        y = np.concatenate(([e_sorted[-1]], e_sorted, [e_sorted[0]]))
        return float(np.interp(az, x, y))


# ---------------------------------------------------------------------------
# Synthetic horizon for the south polar region
# ---------------------------------------------------------------------------

def synthetic_polar_horizon(site_lat_deg: float,
                            site_lon_deg: float,
                            site_elev_m: float = 0.0,
                            mean_ridge_deg: float = 5.0,
                            variability_deg: float = 2.0,
                            n_azimuths: int = 360) -> HorizonProfile:
    """Create an illustrative ridge profile, not measured lunar terrain.

    The lunar south polar region has a high ridge of mountains roughly
    encircling the pole at elevations of ~3-8 degrees (when viewed from
    a low point). This generates a deterministic profile using a Fourier
    sum keyed on the site's longitude — so different longitudes give
    meaningfully different ridge profiles.
    """
    azimuths = np.linspace(0.0, 360.0, n_azimuths, endpoint=False)
    lon = math.radians(site_lon_deg)
    lat = math.radians(site_lat_deg)

    # Base ring of mountains — slightly asymmetric: stronger east & south
    # of the pole, matching the actual Shackleton/Henson/De la Rue geography.
    base = (
        mean_ridge_deg
        + variability_deg * np.sin(np.radians(azimuths) + lon)
        + (variability_deg * 0.6) * np.cos(2 * np.radians(azimuths) - 2 * lon)
    )

    # Add a few discrete peaks (e.g. Shackleton-like) at characteristic azimuths.
    peaks = [
        (15.0 + math.degrees(lon) % 360.0, 4.0),   # generic peak 1
        (210.0 - math.degrees(lon) % 360.0, 3.5),  # generic peak 2
        (90.0 + math.degrees(lon) % 360.0, 2.5),
    ]
    for peak_az, peak_height in peaks:
        sigma = 12.0  # degrees of azimuth spread
        circular_delta = (azimuths - peak_az + 180.0) % 360.0 - 180.0
        base += peak_height * np.exp(-0.5 * (circular_delta / sigma) ** 2)

    # Near-pole sites see slightly higher horizon (you're closer to the rim).
    pole_factor = 1.0 + max(0.0, (90.0 + site_lat_deg) / 90.0) * 0.4  # up to 1.4x
    elevation_deg = np.clip(base * pole_factor, 0.0, None)

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
                         step_m: float = 50.0,
                         elevation_units: str = "m",
                         source_detail: str | None = None,
                         source_url: str | None = None,
                         resolution_m: float | None = None) -> HorizonProfile:
    """Ray trace a lunar DEM with its declared projection and spherical curvature.

    The DEM CRS must describe a Moon-radius ellipsoid and must be transformable
    from lunar longitude/latitude. The requested radius must be covered in
    every azimuth, and the observer height is sampled from the DEM. Missing or
    invalid raster samples are rejected; this function never substitutes a
    synthetic profile.
    """
    try:
        import rasterio  # type: ignore
        from rasterio.crs import CRS  # type: ignore
        from rasterio.warp import transform  # type: ignore
    except Exception as exc:
        raise RuntimeError("LOLA DEM processing requires rasterio; install it before building a profile") from exc

    dem_path = Path(dem_path)
    if not dem_path.exists():
        raise FileNotFoundError(f"Lunar DEM not found: {dem_path}")
    units = elevation_units.strip().lower()
    scale = {"m": 1.0, "metre": 1.0, "meter": 1.0, "km": 1000.0}.get(units)
    if scale is None:
        raise ValueError("elevation_units must be metres ('m') or kilometres ('km')")
    if max_range_km <= 0 or step_m <= 0 or n_azimuths < 8:
        raise ValueError("max_range_km and step_m must be positive; use at least 8 azimuth bins")

    R_moon = 1737400.0
    lunar_geographic = CRS.from_proj4(
        f"+proj=longlat +a={R_moon} +b={R_moon} +no_defs +type=crs"
    )

    with rasterio.open(dem_path) as src:
        if src.crs is None:
            raise ValueError("The lunar DEM has no CRS; define its Moon-centered projection before use")
        if not src.crs.is_projected:
            raise ValueError("The lunar DEM must use a projected lunar CRS")
        crs_parameters = src.crs.to_dict()
        lunar_radius = crs_parameters.get("R", crs_parameters.get("a"))
        if lunar_radius is None or abs(float(lunar_radius) - R_moon) > 1000.0:
            raise ValueError(
                "The DEM CRS does not identify a lunar-radius ellipsoid (~1,737,400 m); "
                "do not treat an Earth EPSG projection as a lunar projection"
            )
        if (
            crs_parameters.get("proj") != "stere"
            or not math.isclose(float(crs_parameters.get("lat_0", 999.0)), -90.0, abs_tol=1e-6)
            or not math.isclose(float(crs_parameters.get("lon_0", 999.0)), 0.0, abs_tol=1e-6)
            or crs_parameters.get("units") != "m"
        ):
            raise ValueError(
                "The DEM must use the expected south-polar stereographic lunar CRS"
            )
        site_lat = math.radians(site_lat_deg)
        site_lon = math.radians(site_lon_deg)
        site_x, site_y = transform(lunar_geographic, src.crs, [site_lon_deg % 360.0], [site_lat_deg])
        site_row, site_col = src.index(site_x[0], site_y[0])
        if not (0 <= site_row < src.height and 0 <= site_col < src.width):
            raise ValueError("The site coordinate falls outside this lunar DEM tile")
        center = next(src.sample([(site_x[0], site_y[0])], indexes=1, masked=True))
        center_value = float(center[0])
        if np.ma.is_masked(center[0]) or not math.isfinite(center_value):
            raise ValueError("The site coordinate has no valid elevation in this lunar DEM")
        if src.nodata is not None and center_value == src.nodata:
            raise ValueError("The site coordinate maps to a DEM no-data cell")
        observer_elevation_m = center_value * scale

        azimuths = np.linspace(0.0, 360.0, n_azimuths, endpoint=False)
        max_alt = np.zeros(n_azimuths)
        max_range_m = max_range_km * 1000.0
        dists = np.arange(step_m, max_range_m + 1e-6, step_m)
        if len(dists) == 0 or max_range_m - dists[-1] > 1e-6:
            dists = np.append(dists, max_range_m)
        for i, az_deg in enumerate(azimuths):
            az = math.radians(az_deg)
            angular_distance = dists / R_moon
            sin_lat2 = (math.sin(site_lat) * np.cos(angular_distance)
                        + math.cos(site_lat) * np.sin(angular_distance) * math.cos(az))
            sample_lats = np.arcsin(np.clip(sin_lat2, -1.0, 1.0))
            sample_lons = site_lon + np.arctan2(
                math.sin(az) * np.sin(angular_distance) * math.cos(site_lat),
                np.cos(angular_distance) - math.sin(site_lat) * np.sin(sample_lats),
            )
            lon_deg = np.rad2deg(sample_lons).tolist()
            lat_deg = np.rad2deg(sample_lats).tolist()
            xs, ys = transform(lunar_geographic, src.crs, lon_deg, lat_deg)
            rows_cols = [src.index(x, y) for x, y in zip(xs, ys)]
            rows = np.asarray([rc[0] for rc in rows_cols], dtype=int)
            cols = np.asarray([rc[1] for rc in rows_cols], dtype=int)
            in_bounds = ((rows >= 0) & (rows < src.height) & (cols >= 0) & (cols < src.width))
            if not np.all(in_bounds):
                raise ValueError(
                    f"The DEM does not cover the full {max_range_km:g} km horizon radius "
                    f"at azimuth {az_deg:.1f}°"
                )
            valid_idx = np.arange(len(dists))
            sampled = np.ma.vstack(list(src.sample(
                ((xs[j], ys[j]) for j in valid_idx), indexes=1, masked=True)))[:, 0]
            sample_values = np.asarray(sampled.filled(np.nan), dtype=float)
            sample_valid = ~np.ma.getmaskarray(sampled) & np.isfinite(sample_values)
            if src.nodata is not None:
                sample_valid &= sample_values != src.nodata
            if not np.all(sample_valid):
                raise ValueError(
                    f"The DEM contains a no-data sample along azimuth {az_deg:.1f}°; "
                    "a complete horizon cannot be derived"
                )
            elevations_m = sample_values * scale
            delta = angular_distance
            radius = R_moon + elevations_m
            east = radius * np.sin(delta)
            up = radius * np.cos(delta) - (R_moon + observer_elevation_m)
            altitude = np.rad2deg(np.arctan2(up, east))
            max_alt[i] = float(np.clip(np.nanmax(altitude), 0.0, 90.0))

        return HorizonProfile(
            azimuth_deg=azimuths,
            elevation_deg=max_alt,
            site_lat_deg=site_lat_deg,
            site_lon_deg=site_lon_deg,
            site_elev_m=observer_elevation_m,
            source="dem",
            coverage_range_km=float(max_range_km),
            source_detail=source_detail or dem_path.name,
            source_url=source_url,
            resolution_m=resolution_m,
        )


# ---------------------------------------------------------------------------
# Convenience: bundled default horizon per site
# ---------------------------------------------------------------------------

DEFAULT_HORIZON_DIR = Path(__file__).resolve().parent.parent / "data" / "horizons"
_DYNAMIC_PROFILE_CACHE: dict[str, HorizonProfile] = {}


def horizon_for_site(site_id: str,
                     site_lat_deg: float,
                     site_lon_deg: float,
                     site_elev_m: float = 0.0,
                     *,
                     generate_from_tiles: bool = False) -> HorizonProfile:
    """Return a location-matched profile, optionally deriving one from LOLA.

    Saved profiles are accepted only at their stored coordinates. When a
    request asks for terrain, bundled tiles are ray traced at the widest radius
    they completely cover; the radius is preserved in the returned profile.
    """
    path = DEFAULT_HORIZON_DIR / f"{site_id}.json"
    if path.exists():
        profile = HorizonProfile.load(path)
        same_location = (
            math.isclose(profile.site_lat_deg, site_lat_deg, abs_tol=1e-6)
            and math.isclose(profile.site_lon_deg % 360.0, site_lon_deg % 360.0, abs_tol=1e-6)
        )
        if same_location and (profile.source == "dem" or not generate_from_tiles):
            return profile

    if generate_from_tiles:
        terrain_dir = Path(__file__).resolve().parent.parent / "data" / "terrain" / "lola"
        dem_paths = sorted(terrain_dir.glob("*_final_adj_5mpp_surf.tif"))
        tile_signature = "|".join(
            f"{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
            for path in dem_paths
        )
        key = hashlib.sha256(
            f"{site_lat_deg:.8f},{site_lon_deg % 360.0:.8f}|{tile_signature}".encode("ascii")
        ).hexdigest()[:16]
        if key in _DYNAMIC_PROFILE_CACHE:
            return _DYNAMIC_PROFILE_CACHE[key]
        cache_path = DEFAULT_HORIZON_DIR / "generated" / f"{key}.json"
        if cache_path.exists():
            cached = HorizonProfile.load(cache_path)
            if (
                cached.source == "dem"
                and math.isclose(cached.site_lat_deg, site_lat_deg, abs_tol=1e-6)
                and math.isclose(cached.site_lon_deg % 360.0, site_lon_deg % 360.0, abs_tol=1e-6)
            ):
                _DYNAMIC_PROFILE_CACHE[key] = cached
                return cached
        for dem_path in dem_paths:
            tile_id = dem_path.name.split("_", maxsplit=1)[0]
            source_detail = (
                f"NASA GSFC PGDA LRO-LOLA adjusted LDEM {tile_id}, "
                "5 m/pixel; interpolated elevation grid"
            )
            for radius_km in (5.0, 3.0, 2.0, 1.0, 0.5, 0.25):
                try:
                    profile = build_horizon_profile(
                        site_lat_deg,
                        site_lon_deg,
                        site_elev_m,
                        dem_path,
                        max_range_km=radius_km,
                        n_azimuths=360,
                        step_m=25.0,
                        elevation_units="m",
                        source_detail=source_detail,
                        source_url="https://pgda.gsfc.nasa.gov/products/78",
                        resolution_m=5.0,
                    )
                except (ValueError, RuntimeError):
                    continue
                _DYNAMIC_PROFILE_CACHE[key] = profile
                try:
                    profile.save(cache_path)
                except OSError:
                    # Read-only deployments can reuse the in-process profile.
                    pass
                return profile
    return synthetic_polar_horizon(site_lat_deg, site_lon_deg, site_elev_m)
