"""Build local horizon masks from bundled NASA GSFC PGDA LOLA DEM tiles.

Run from the repository root after the source GeoTIFF tiles are present:
    python data_pipeline/build_lola_horizons.py

The script only creates a terrain profile when a tile covers the complete
requested radius around a candidate site in every azimuth. It never extrapolates
terrain or silently substitutes a synthetic profile.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.horizon import build_horizon_profile
from src.sites import all_sites

TERRAIN_DIR = ROOT / "data" / "terrain" / "lola"
PROFILE_DIR = ROOT / "data" / "horizons"
PROVENANCE_PATH = TERRAIN_DIR / "provenance.json"
PGDA_PRODUCT_URL = "https://pgda.gsfc.nasa.gov/products/78"
SOURCE_DATASET_DOI = "10.17189/1520642"
PROFILE_RANGES_KM = (5.0, 3.0, 2.0, 1.0, 0.5, 0.25)
RAY_STEP_M = 25.0
REGION_NAMES = {
    "Site01": "Connecting Ridge",
    "Site04": "Shackleton Rim",
    "Site07": "Peak near Shackleton",
    "Site20": "Leibnitz Beta Plateau",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tile_center(path: Path, tile_id: str) -> dict[str, object]:
    moon_radius_m = 1_737_400.0
    lunar_geographic = CRS.from_proj4(
        f"+proj=longlat +a={moon_radius_m} +b={moon_radius_m} +no_defs +type=crs"
    )
    with rasterio.open(path) as src:
        x = (src.bounds.left + src.bounds.right) / 2.0
        y = (src.bounds.bottom + src.bounds.top) / 2.0
        longitude, latitude = transform(src.crs, lunar_geographic, [x], [y])
        center_sample = next(src.sample([(x, y)], indexes=1, masked=True))[0]
        if np.ma.is_masked(center_sample) or not np.isfinite(float(center_sample)):
            raise ValueError(f"LOLA tile has no valid elevation at its center: {path}")
        return {
            "tile_id": tile_id,
            "region_name": REGION_NAMES.get(tile_id, tile_id),
            "center_latitude_deg": float(latitude[0]),
            "center_longitude_deg_east": float(longitude[0] % 360.0),
            "center_elevation_m": float(center_sample),
            "center_x_m": float(x),
            "center_y_m": float(y),
            "bounds_m": {
                "left": float(src.bounds.left),
                "bottom": float(src.bounds.bottom),
                "right": float(src.bounds.right),
                "top": float(src.bounds.top),
            },
            "resolution_m": 5.0,
            "coordinate_basis": "Georeferenced center of this regional DEM tile; a terrain-data sample location, not a surveyed landing site.",
        }


def build() -> dict[str, object]:
    if not TERRAIN_DIR.exists():
        raise FileNotFoundError(f"LOLA source directory not found: {TERRAIN_DIR}")
    tiles = sorted(TERRAIN_DIR.glob("*_final_adj_5mpp_surf.tif"))
    if not tiles:
        raise FileNotFoundError(
            "No PGDA LOLA tiles found. Download the listed files in "
            "data/terrain/lola/README.md first."
        )

    built: dict[str, dict[str, object]] = {}
    tile_manifest: list[dict[str, object]] = []
    for tile_path in tiles:
        tile_id = tile_path.name.split("_", maxsplit=1)[0]
        source_detail = (
            f"NASA GSFC PGDA LRO-LOLA adjusted LDEM {tile_id}, "
            "5 m/pixel; interpolated elevation grid"
        )
        tile_url = f"https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/{tile_id}/{tile_path.name}"
        tile_manifest.append({
            "file": tile_path.relative_to(ROOT).as_posix(),
            "bytes": tile_path.stat().st_size,
            "sha256": _sha256(tile_path),
            "url": tile_url,
            "product_page": PGDA_PRODUCT_URL,
            **_tile_center(tile_path, tile_id),
        })

        for site in all_sites():
            profile = None
            for radius_km in PROFILE_RANGES_KM:
                try:
                    profile = build_horizon_profile(
                        site.lat_deg,
                        site.lon_deg,
                        site.elev_m,
                        tile_path,
                        max_range_km=radius_km,
                        n_azimuths=360,
                        step_m=RAY_STEP_M,
                        elevation_units="m",
                        source_detail=source_detail,
                        source_url=PGDA_PRODUCT_URL,
                        resolution_m=5.0,
                    )
                    break
                except (ValueError, RuntimeError):
                    continue
            if profile is None:
                continue

            current = built.get(site.site_id)
            if current is not None:
                # Keep the profile from the tile with the larger actual radius.
                current_range = float(current["coverage_range_km"])
                if current_range >= float(profile.coverage_range_km or 0.0):
                    continue
            profile.save(PROFILE_DIR / f"{site.site_id}.json")
            built[site.site_id] = {
                "site_id": site.site_id,
                "site_name": site.name,
                "latitude_deg": site.lat_deg,
                "longitude_deg_east": site.lon_deg % 360.0,
                "dem_surface_elevation_m": profile.site_elev_m,
                "source_detail": profile.source_detail,
                "source_url": profile.source_url,
                "coverage_range_km": profile.coverage_range_km,
                "resolution_m": profile.resolution_m,
                "profile_file": f"data/horizons/{site.site_id}.json",
            }

    profile_manifest: dict[str, object] = {
        "title": "LOLA-derived terrain horizons for Lunar Horizon",
        "source_instrument": "Lunar Orbiter Laser Altimeter (LOLA) aboard Lunar Reconnaissance Orbiter",
        "source_archive": "NASA Planetary Data System Geosciences Node / NASA GSFC PGDA",
        "source_dataset_doi": SOURCE_DATASET_DOI,
        "product_page": PGDA_PRODUCT_URL,
        "product_description": (
            "PGDA south-polar, track-adjusted 5 m/pixel LDEM GeoTIFFs derived from LRO-LOLA laser altimetry. "
            "The elevation maps are interpolated grids; pixel spacing is not equivalent to independent 5 m measurements."
        ),
        "coordinate_frame": "South-polar stereographic X/Y, MOON_ME reference frame of ephemeris DE421",
        "vertical_units": "metres",
        "profiles_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile_method": {
            "description": "Great-circle rays over the lunar sphere; terrain elevation is measured relative to the DEM value at the observer; the maximum obstruction angle is stored in each azimuth bin.",
            "ray_azimuth_bins": 360,
            "ray_step_m": RAY_STEP_M,
            "preferred_profile_range_km": PROFILE_RANGES_KM[0],
            "minimum_profile_range_km": PROFILE_RANGES_KM[-1],
            "applied_only_when_every_azimuth_has_complete_valid_DEM_coverage": True,
        },
        "tiles": tile_manifest,
        "site_profiles": list(built.values()),
        "sites_without_terrain_profile": [
            site.site_id for site in all_sites() if site.site_id not in built
        ],
        "limitations": [
            "Site coordinates are the prototype's nominal points, not surveyed landing locations.",
            "A site without a complete radius of at least 0.25 km in a bundled tile keeps geometric visibility; profiles below 5 km represent only the stated local radius.",
            "The regional DEM products include interpolation and do not establish local terrain accuracy at every 5 m pixel.",
        ],
    }
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    TERRAIN_DIR.mkdir(parents=True, exist_ok=True)
    PROVENANCE_PATH.write_text(json.dumps(profile_manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "profiles_built": list(built),
        "sites_without_terrain_profile": profile_manifest["sites_without_terrain_profile"],
        "provenance_file": PROVENANCE_PATH.relative_to(ROOT).as_posix(),
    }, indent=2))
    return profile_manifest


if __name__ == "__main__":
    build()
