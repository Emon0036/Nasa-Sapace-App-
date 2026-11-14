"""Validate cached 6-hour Horizons interpolation against direct 15-minute JPL data.

When a usable CSPICE installation is present, the script also compares the
local SPICE calculation against the same direct JPL Horizons observer output.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import ephemeris
from src.horizons import query_site_ephemeris
from src.sites import get_site

TRAINING_DATA = ROOT / "data" / "processed" / "horizons_ephemeris.csv"
OUTPUT = ROOT / "data" / "processed" / "ephemeris_validation.json"
CASE_SITES = ("shackleton_henson", "shackleton_rim_e", "flat_reference", "peary", "south_pole_reference")
CASE_DATES = ("2026-06-01", "2026-09-01", "2026-12-01", "2027-03-01")
TRANSITION_CASES = (
    ("flat_reference", "2026-08-20T12:00:00Z"),
    ("shackleton_henson", "2026-06-07T12:00:00Z"),
    ("shackleton_rim_e", "2026-08-12T00:00:00Z"),
    ("shackleton_rim_n", "2026-07-26T18:00:00Z"),
)


def _circular_error(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    return np.abs((actual - predicted + 180.0) % 360.0 - 180.0)


def _interpolate_training(site_rows: pd.DataFrame, times: pd.DatetimeIndex) -> pd.DataFrame:
    base_time = pd.DatetimeIndex(pd.to_datetime(site_rows["time_utc"], utc=True))
    base_seconds = base_time.asi8.astype(np.float64) / 1e9
    target_seconds = times.asi8.astype(np.float64) / 1e9
    result = pd.DataFrame({"time_utc": times})
    for name in ("sun_alt_deg", "earth_alt_deg"):
        result[name] = np.interp(target_seconds, base_seconds, site_rows[name].to_numpy(dtype=float))
    for target in ("sun", "earth"):
        azimuth = np.deg2rad(site_rows[f"{target}_az_deg"].to_numpy(dtype=float))
        sin_value = np.interp(target_seconds, base_seconds, np.sin(azimuth))
        cos_value = np.interp(target_seconds, base_seconds, np.cos(azimuth))
        result[f"{target}_az_deg"] = np.rad2deg(np.arctan2(sin_value, cos_value)) % 360.0
    return result


def validate() -> dict[str, object]:
    if not TRAINING_DATA.exists():
        raise FileNotFoundError("Run data_pipeline/collect_nasa_data.py first")
    data = pd.read_csv(TRAINING_DATA, parse_dates=["time_utc"])
    site_results: list[dict[str, object]] = []
    spice_errors: list[dict[str, float]] = []

    validation_cases = [(site_id, date_text) for site_id in CASE_SITES for date_text in CASE_DATES]
    validation_cases.extend(TRANSITION_CASES)
    for site_id, date_text in validation_cases:
        site = get_site(site_id)
        training_site = data[data["site_id"] == site_id].sort_values("time_utc")
        if training_site.empty:
            continue
        start = pd.Timestamp(date_text)
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        else:
            start = start.tz_convert("UTC")
        times = pd.date_range(start=start, periods=97, freq="15min")
        cache_token = start.strftime("%Y%m%d") if start.hour == 0 and start.minute == 0 else start.strftime("%Y%m%dT%H%M")
        direct, source = query_site_ephemeris(
            times, site.lat_deg, site.lon_deg, site.elev_m,
            site_id=f"validation_{site_id}_{cache_token}",
        )
        approximate = _interpolate_training(training_site, times)
        row: dict[str, object] = {
            "site_id": site_id,
            "site_name": site.name,
            "date_utc": start.date().isoformat(),
            "window_start_utc": start.isoformat(),
            "source": source,
            "samples": int(len(times)),
        }
        for target in ("sun", "earth"):
            altitude = direct[f"{target}_alt_deg"].to_numpy(dtype=float)
            geometric_visible = altitude > 0.0
            row[f"{target}_altitude_min_deg"] = float(np.min(altitude))
            row[f"{target}_altitude_max_deg"] = float(np.max(altitude))
            row[f"{target}_near_horizon_samples_within_0_25_deg"] = int(np.count_nonzero(np.abs(altitude) <= 0.25))
            row[f"{target}_geometric_horizon_transitions"] = int(np.count_nonzero(geometric_visible[1:] != geometric_visible[:-1]))
        for target in ("sun", "earth"):
            alt_error = np.abs(direct[f"{target}_alt_deg"].to_numpy()
                               - approximate[f"{target}_alt_deg"].to_numpy())
            az_error = _circular_error(direct[f"{target}_az_deg"].to_numpy(),
                                       approximate[f"{target}_az_deg"].to_numpy())
            row[f"{target}_alt_mae_deg"] = float(np.mean(alt_error))
            row[f"{target}_alt_p95_deg"] = float(np.percentile(alt_error, 95))
            row[f"{target}_alt_max_deg"] = float(np.max(alt_error))
            row[f"{target}_az_circular_mae_deg"] = float(np.mean(az_error))
            row[f"{target}_az_circular_p95_deg"] = float(np.percentile(az_error, 95))

        if ephemeris.using_spice():
            local = ephemeris.compute_sky(
                times.to_pydatetime(), site.lat_deg, site.lon_deg, site.elev_m,
                site_id=site_id,
            )
            spice_row: dict[str, float] = {"site_id": site_id, "date": date_text}
            for target, alt_attr, az_attr in (
                ("sun", "sun_alt", "sun_az"), ("earth", "earth_alt", "earth_az"),
            ):
                alt_error = np.abs(direct[f"{target}_alt_deg"].to_numpy() - getattr(local, alt_attr))
                az_error = _circular_error(direct[f"{target}_az_deg"].to_numpy(), getattr(local, az_attr))
                spice_row[f"{target}_alt_mae_deg"] = float(np.mean(alt_error))
                spice_row[f"{target}_alt_max_deg"] = float(np.max(alt_error))
                spice_row[f"{target}_az_mae_deg"] = float(np.mean(az_error))
                spice_row[f"{target}_az_max_deg"] = float(np.max(az_error))
            spice_errors.append(spice_row)
        site_results.append(row)

    validation = {
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_source": "NASA/JPL Horizons observer API, DE solution identified in each raw response",
        "comparison": "Linear 6-hour cached Horizons interpolation versus direct 15-minute Horizons output; azimuth errors are circular.",
        "sites": list(CASE_SITES),
        "dates_utc": list(CASE_DATES),
        "transition_case_windows": [
            {"site_id": site_id, "start_utc": start} for site_id, start in TRANSITION_CASES
        ],
        "case_count": len(site_results),
        "interpolation_cases": site_results,
        "spice_status": "available" if ephemeris.using_spice() else "unavailable in this runtime; no local-SPICE error claim",
        "spice_direct_comparison": spice_errors,
        "limitations": [
            "Horizons comparisons share the same JPL reference service and are not independent instrument validation.",
            "Candidate site coordinates are nominal prototype points.",
            "No LOLA terrain horizon was available for these comparisons.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    return validation


if __name__ == "__main__":
    validate()
