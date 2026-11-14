"""Build a site horizon profile from a correctly referenced lunar DEM.

Example:
    python data_pipeline/process_terrain.py --site-id shackleton_henson \
      --lat -89.45 --lon 160 --elev-m 1450 --dem dem/your_lola_tile.tif \
      --product-id LDEM_PRODUCT_ID --source-url https://pgda.gsfc.nasa.gov/...

The DEM must have a Moon-radius CRS and elevations in metres (or explicitly
pass ``--elevation-units km``). No synthetic fallback is generated on error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.horizon import build_horizon_profile

def process(args: argparse.Namespace) -> Path:
    dem_path = Path(args.dem).resolve()
    if not dem_path.is_file():
        raise FileNotFoundError(f"DEM does not exist: {dem_path}")
    profile = build_horizon_profile(
        site_lat_deg=args.lat,
        site_lon_deg=args.lon,
        site_elev_m=args.elev_m,
        dem_path=dem_path,
        max_range_km=args.max_range_km,
        n_azimuths=args.azimuths,
        step_m=args.step_m,
        elevation_units=args.elevation_units,
    )
    out_dir = ROOT / "data" / "horizons"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{args.site_id}.json"
    profile.save(output)
    digest = hashlib.sha256()
    with dem_path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()
    crs = "unknown"
    try:
        import rasterio  # type: ignore
        with rasterio.open(dem_path) as src:
            crs = src.crs.to_string() if src.crs else "missing"
    except Exception:
        pass
    provenance = {
        "profile_path": str(output.relative_to(ROOT)).replace("\\", "/"),
        "source_url": args.source_url,
        "product_id": args.product_id,
        "acquired_at_utc": args.acquired_at_utc,
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "original_file": str(dem_path),
        "sha256": checksum,
        "raster_crs": crs,
        "coordinate_frame": "Lunar longitude/latitude transformed into the raster's Moon-centered CRS",
        "elevation_units": args.elevation_units,
        "site": {"id": args.site_id, "latitude_deg": args.lat,
                 "longitude_deg_east": args.lon, "elevation_m": args.elev_m},
        "processing": {"max_range_km": args.max_range_km,
                       "azimuth_bins": args.azimuths,
                       "sample_step_m": args.step_m,
                       "terrain_curvature": "spherical lunar radius 1,737,400 m"},
        "profile_source": profile.source,
    }
    output.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-id", required=True)
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--elev-m", required=True, type=float)
    parser.add_argument("--dem", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--acquired-at-utc", default="unknown")
    parser.add_argument("--elevation-units", choices=("m", "km"), default="m")
    parser.add_argument("--max-range-km", type=float, default=30.0)
    parser.add_argument("--azimuths", type=int, default=360)
    parser.add_argument("--step-m", type=float, default=50.0)
    process(parser.parse_args())


if __name__ == "__main__":
    main()
