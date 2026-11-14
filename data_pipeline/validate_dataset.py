"""Validate the prepared NASA/JPL Horizons ephemeris table and its provenance."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "processed" / "horizons_ephemeris.csv"
MANIFEST = ROOT / "data" / "processed" / "horizons_ephemeris.provenance.json"


def validate() -> dict[str, object]:
    if not DATASET.is_file() or not MANIFEST.is_file():
        raise FileNotFoundError("Run data_pipeline/collect_nasa_data.py first")
    frame = pd.read_csv(DATASET, parse_dates=["time_utc"])
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    required = {
        "site_id", "time_utc", "latitude_deg", "longitude_deg_east", "elevation_m",
        "sun_alt_deg", "sun_az_deg", "earth_alt_deg", "earth_az_deg", "ephemeris_source",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if frame.empty or frame[list(required)].isna().any().any():
        raise ValueError("Dataset is empty or contains missing required values")
    if frame.duplicated(["site_id", "time_utc"]).any():
        raise ValueError("Duplicate site/time keys found")
    for column in ("sun_alt_deg", "earth_alt_deg"):
        if not frame[column].between(-90.5, 90.5).all():
            raise ValueError(f"Altitude out of range in {column}")
    for column in ("sun_az_deg", "earth_az_deg"):
        if not frame[column].between(0.0, 360.0, inclusive="left").all():
            raise ValueError(f"Azimuth out of range in {column}")
    if len(frame) != int(manifest.get("row_count", -1)):
        raise ValueError("Manifest row count does not match the data")
    if "Horizons" not in " ".join(frame["ephemeris_source"].astype(str).unique()):
        raise ValueError("Source labels do not identify JPL Horizons")

    south_pole = frame[frame["latitude_deg"] <= -89.0]
    exact_south_pole = frame[frame["latitude_deg"] == -90.0]
    return {
        "row_count": int(len(frame)),
        "site_count": int(frame["site_id"].nunique()),
        "time_start_utc": frame["time_utc"].min().isoformat(),
        "time_stop_utc": frame["time_utc"].max().isoformat(),
        "sources": sorted(frame["ephemeris_source"].astype(str).unique().tolist()),
        "south_polar_sun_altitude_min_deg": float(south_pole["sun_alt_deg"].min()) if not south_pole.empty else None,
        "south_polar_sun_altitude_max_deg": float(south_pole["sun_alt_deg"].max()) if not south_pole.empty else None,
        "exact_south_pole_sun_altitude_min_deg": float(exact_south_pole["sun_alt_deg"].min()) if not exact_south_pole.empty else None,
        "exact_south_pole_sun_altitude_max_deg": float(exact_south_pole["sun_alt_deg"].max()) if not exact_south_pole.empty else None,
        "dataset_path": str(DATASET.relative_to(ROOT)).replace("\\", "/"),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
