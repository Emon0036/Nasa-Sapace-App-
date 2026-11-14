"""Acquire topocentric Sun/Earth ephemerides from NASA/JPL Horizons.

Example:
    python data_pipeline/collect_nasa_data.py --start 2026-06-01 --stop 2027-06-01 --step 6h

Raw Horizons JSON responses are cached under ``data/raw/horizons_cache``.
The processed, one-row-per-site-and-time table is written to
``data/processed/horizons_ephemeris.csv`` with a provenance manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.horizons import query_site_ephemeris
from src.sites import all_sites, get_site

OUT_DIR = ROOT / "data" / "processed"
DATASET_PATH = OUT_DIR / "horizons_ephemeris.csv"
MANIFEST_PATH = OUT_DIR / "horizons_ephemeris.provenance.json"


def _build_time_index(start: str, stop: str, step: str) -> pd.DatetimeIndex:
    start_ts = pd.Timestamp(start, tz="UTC")
    stop_ts = pd.Timestamp(stop, tz="UTC")
    index = pd.date_range(start=start_ts, end=stop_ts, freq=step)
    if len(index) < 2 or index[-1] != stop_ts:
        raise ValueError("The stop time must be an exact multiple of --step after --start")
    return index


def collect(
    start: str = "2026-06-01",
    stop: str = "2027-06-01",
    step: str = "6h",
    site_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Collect and persist the Horizons training/validation dataset."""
    times = _build_time_index(start, stop, step)
    sites = [get_site(site_id) for site_id in site_ids] if site_ids else all_sites()
    rows: list[pd.DataFrame] = []
    for site in sites:
        print(f"Querying {site.name}: {len(times):,} samples at {step} cadence")
        frame, source = query_site_ephemeris(
            times,
            site.lat_deg,
            site.lon_deg,
            site.elev_m,
            site_id=site.site_id,
        )
        frame.insert(0, "site_id", site.site_id)
        frame.insert(1, "site_name", site.name)
        frame["latitude_deg"] = site.lat_deg
        frame["longitude_deg_east"] = site.lon_deg % 360.0
        frame["elevation_m"] = site.elev_m
        frame["ephemeris_source"] = source
        frame["coordinate_frame"] = "Horizons high-precision lunar ME geodetic observer"
        rows.append(frame)

    dataset = pd.concat(rows, ignore_index=True)
    dataset["time_utc"] = pd.to_datetime(dataset["time_utc"], utc=True)
    dataset = dataset.sort_values(["site_id", "time_utc"]).reset_index(drop=True)
    if dataset.isna().any().any():
        raise RuntimeError("The collected Horizons dataset contains missing values")
    if dataset.duplicated(["site_id", "time_utc"]).any():
        raise RuntimeError("The collected Horizons dataset contains duplicate site/time rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(DATASET_PATH, index=False, float_format="%.8f")
    manifest = {
        "title": "Lunar Horizon topocentric ephemeris training and validation data",
        "source_url": "https://ssd.jpl.nasa.gov/api/horizons.api",
        "documentation_url": "https://ssd-api.jpl.nasa.gov/doc/horizons.html",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "retrieval_method": "Horizons API observer ephemeris; apparent airless azimuth/elevation (quantity 4)",
        "target_solution": sorted(dataset["ephemeris_source"].unique().tolist()),
        "targets": {"sun": "10", "earth": "399"},
        "observer_center": "coord@301 (Moon surface site)",
        "observer_coordinate_type": "GEODETIC",
        "coordinate_frame": "Horizons high-precision lunar mean-Earth (ME) observer frame",
        "longitude_convention": "East-positive degrees",
        "latitude_convention": "Planetographic/geodetic degrees",
        "elevation_input_units": "metres in this CSV; converted to kilometres for Horizons SITE_COORD",
        "output_units": {"azimuth": "degrees clockwise from north", "altitude": "degrees above local horizontal"},
        "time_standard": "UTC",
        "requested_start_utc": times[0].isoformat(),
        "requested_stop_utc": times[-1].isoformat(),
        "requested_step": step,
        "site_coordinate_note": "Candidate coordinates/elevations are the existing prototype's nominal points, not verified landing survey data; the exact South Pole row is an idealized geometry reference, not a landing site.",
        "label_provenance": "JPL Horizons DE ephemeris calculations; not spacecraft observations and not fabricated measurements.",
        "processing_steps": [
            "Query Sun and Earth separately for each lunar surface observer.",
            "Parse Horizons $$SOE/$$EOE output rows and align the UTC timestamps.",
            "Store apparent, airless topocentric azimuth/elevation in degrees.",
            "Retain site coordinates, source solution, and frame metadata per row.",
        ],
        "dataset_path": str(DATASET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "row_count": int(len(dataset)),
        "site_ids": [site.site_id for site in sites],
        "columns": list(dataset.columns),
        "raw_response_cache": "data/raw/horizons_cache/ (one JSON response and provenance sidecar per target/query)",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(dataset):,} rows to {DATASET_PATH}")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-06-01", help="UTC start date/time")
    parser.add_argument("--stop", default="2027-06-01", help="UTC stop date/time")
    parser.add_argument("--step", default="6h", help="Horizons cadence, e.g. 6h or 30m")
    parser.add_argument("--site-ids", nargs="*", help="Optional site IDs; default collects all existing sites")
    args = parser.parse_args()
    collect(args.start, args.stop, args.step, args.site_ids)


if __name__ == "__main__":
    main()
