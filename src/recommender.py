"""Explainable scenario ranking backed by the Horizons-trained ML surrogate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd

from ml.features import FEATURE_NAMES, make_features
from . import analysis, horizon
from .sites import Site

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "ml" / "models" / "lunar_conditions_rf.joblib"
MISSION_SCORE_WEIGHTS = {"sunlight": 0.60, "earth_visibility": 0.40}


def load_model() -> dict:
    if not MODEL_PATH.exists():
        raise FileNotFoundError("ML model is missing; run ml/train_model.py first")
    model = joblib.load(MODEL_PATH)
    if model.get("feature_names") != FEATURE_NAMES:
        raise ValueError("ML model feature schema does not match this version of the app")
    return model


def _model_inputs(times: pd.DatetimeIndex, site: Site) -> pd.DataFrame:
    return pd.DataFrame({
        "time_utc": times,
        "latitude_deg": site.lat_deg,
        "longitude_deg_east": site.lon_deg % 360.0,
        "elevation_m": site.elev_m,
    })


def _nearest_training_location_deg(site: Site, model: dict) -> float:
    locations = model.get("training_locations", [])
    if not locations:
        return float("inf")
    lat1 = np.deg2rad(site.lat_deg)
    lon1 = np.deg2rad(site.lon_deg % 360.0)
    best = float("inf")
    for location in locations:
        lat2 = np.deg2rad(float(location["latitude_deg"]))
        lon2 = np.deg2rad(float(location["longitude_deg_east"]) % 360.0)
        dlat = lat2 - lat1
        dlon = (lon2 - lon1 + np.pi) % (2.0 * np.pi) - np.pi
        haversine = (np.sin(dlat / 2.0) ** 2
                     + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2)
        central_angle = 2.0 * np.arcsin(np.sqrt(np.clip(haversine, 0.0, 1.0)))
        best = min(best, float(np.rad2deg(central_angle)))
    return best


def _predict(model: dict, times: pd.DatetimeIndex, site: Site) -> pd.DataFrame:
    inputs = _model_inputs(times, site)
    features = make_features(inputs)
    altitudes = np.asarray(model["altitude_model"].predict(features), dtype=float)
    az_vectors = np.asarray(model["azimuth_model"].predict(features), dtype=float)
    sun_az = np.rad2deg(np.arctan2(az_vectors[:, 0], az_vectors[:, 1])) % 360.0
    earth_az = np.rad2deg(np.arctan2(az_vectors[:, 2], az_vectors[:, 3])) % 360.0
    return pd.DataFrame({
        "time_utc": times,
        "sun_alt_deg": altitudes[:, 0],
        "sun_az_deg": sun_az,
        "earth_alt_deg": altitudes[:, 1],
        "earth_az_deg": earth_az,
    })


def _summary_for_candidate(
    model: dict,
    site: Site,
    start_utc: datetime,
    duration_hours: float,
    profile: horizon.HorizonProfile,
    sample_hours: float,
) -> dict[str, object]:
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    stop = start_utc + timedelta(hours=duration_hours)
    model_start = pd.Timestamp(model["date_min_utc"])
    model_stop = pd.Timestamp(model["date_max_utc"])
    if pd.Timestamp(start_utc) < model_start or pd.Timestamp(stop) > model_stop:
        raise ValueError(
            f"ML training coverage is {model_start.isoformat()} through {model_stop.isoformat()}; "
            "choose a scenario window inside those dates"
        )
    bounds = model.get("coordinate_bounds", {})
    for key, value in (
        ("latitude_deg", site.lat_deg),
        ("elevation_m", site.elev_m),
    ):
        if key in bounds and not bounds[key][0] <= value <= bounds[key][1]:
            raise ValueError(f"Site {key} is outside the ML training coverage")
    step_minutes = max(1, int(round(sample_hours * 60.0)))
    times = pd.date_range(start=start_utc, end=stop, freq=f"{step_minutes}min", tz="UTC")
    if times[-1] != pd.Timestamp(stop):
        times = times.append(pd.DatetimeIndex([pd.Timestamp(stop)]))
    predicted = _predict(model, times, site)

    # Synthetic horizon curves remain visual aids and are excluded from the
    # mission score; use a profile only when its source is a processed LOLA DEM.
    measured_dem = profile.source == "dem"
    if measured_dem:
        sun_threshold = np.asarray([profile.horizon_altitude_at(v) for v in predicted["sun_az_deg"]])
        earth_threshold = np.asarray([profile.horizon_altitude_at(v) for v in predicted["earth_az_deg"]])
    else:
        sun_threshold = np.zeros(len(predicted), dtype=float)
        earth_threshold = np.zeros(len(predicted), dtype=float)
    sun_visible = predicted["sun_alt_deg"].to_numpy() > sun_threshold
    earth_visible = predicted["earth_alt_deg"].to_numpy() > earth_threshold
    interval_hours = duration_hours / max(1, len(times) - 1)
    sun_runs = analysis._continuous_runs(sun_visible, interval_hours)
    earth_blackouts = analysis._continuous_runs(~earth_visible, interval_hours)
    sun_pct = float(sun_visible.mean() * 100.0)
    earth_pct = float(earth_visible.mean() * 100.0)
    score = (
        MISSION_SCORE_WEIGHTS["sunlight"] * sun_pct
        + MISSION_SCORE_WEIGHTS["earth_visibility"] * earth_pct
    )
    return {
        "site_id": site.site_id,
        "site_name": site.name,
        "delay_hours": float((start_utc - getattr(site, "_base_time", start_utc)).total_seconds() / 3600.0),
        "start_utc": start_utc.isoformat(),
        "sun_above_geometric_horizon_pct": sun_pct,
        "earth_above_geometric_horizon_pct": earth_pct,
        "max_sunlit_streak_h": float(max(sun_runs, default=0.0)),
        "max_earth_blackout_min": float(max(earth_blackouts, default=0.0) * 60.0),
        "score": float(score),
        "terrain_basis": (
            f"LOLA-derived DEM within {profile.coverage_range_km:g} km"
            if measured_dem and profile.coverage_range_km is not None
            else "LOLA-derived DEM profile" if measured_dem
            else "geometric horizon; no LOLA terrain mask"
        ),
        "sample_count": int(len(times)),
        "model_date_min_utc": model["date_min_utc"],
        "model_date_max_utc": model["date_max_utc"],
    }


def rank_scenarios(
    sites: Iterable[Site],
    start_utc: datetime,
    duration_hours: float,
    profiles: dict[str, horizon.HorizonProfile] | None = None,
    *,
    delays_hours: tuple[int, ...] = (0, 24, 48),
    sample_hours: float = 3.0,
) -> pd.DataFrame:
    """Rank site/date candidates and return the score components for explanation."""
    model = load_model()
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    profiles = profiles or {}
    requested_sites = list(sites)
    supported_sites = [
        site for site in requested_sites
        if site.site_id in model.get("site_ids", [])
        or _nearest_training_location_deg(site, model) <= 5.0
    ]
    excluded_sites = [site.name for site in requested_sites if site not in supported_sites]
    if not supported_sites:
        raise ValueError(
            "No selected site is within 5° of a training location; the model will not extrapolate outside its sampled sites"
        )
    rows: list[dict[str, object]] = []
    for site in supported_sites:
        profile = profiles.get(site.site_id) or horizon.horizon_for_site(
            site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
        for delay in delays_hours:
            scenario_start = start_utc + timedelta(hours=delay)
            row = _summary_for_candidate(
                model, site, scenario_start, duration_hours, profile, sample_hours)
            row["delay_hours"] = float(delay)
            row["sunlight_weight"] = MISSION_SCORE_WEIGHTS["sunlight"]
            row["earth_visibility_weight"] = MISSION_SCORE_WEIGHTS["earth_visibility"]
            row["explanation"] = (
                f"Predicted sunlight clears the geometric horizon for {row['sun_above_geometric_horizon_pct']:.1f}% "
                f"of samples and Earth is visible for {row['earth_above_geometric_horizon_pct']:.1f}%. "
                f"Score = 60% sunlight + 40% Earth visibility. {row['terrain_basis']}."
            )
            rows.append(row)
    result = pd.DataFrame(rows).sort_values(
        ["score", "sun_above_geometric_horizon_pct", "earth_above_geometric_horizon_pct"],
        ascending=False,
    ).reset_index(drop=True)
    result.insert(0, "rank", np.arange(1, len(result) + 1))
    result.attrs["excluded_sites"] = excluded_sites
    return result
