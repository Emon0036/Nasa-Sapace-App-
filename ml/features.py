"""Shared cyclical feature engineering for lunar geometry models."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "latitude_deg",
    "longitude_sin",
    "longitude_cos",
    "elevation_km",
    "annual_sin",
    "annual_cos",
    "synodic_sin",
    "synodic_cos",
    "sidereal_sin",
    "sidereal_cos",
    "anomalistic_sin",
    "anomalistic_cos",
]

_J2000 = pd.Timestamp("2000-01-01T12:00:00Z")
_SYNODIC_MONTH_DAYS = 29.530588853
_SIDEREAL_MONTH_DAYS = 27.321661
_ANOMALISTIC_MONTH_DAYS = 27.554550


def make_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build stable cyclical time and observer features from a Horizons table."""
    times = pd.DatetimeIndex(pd.to_datetime(frame["time_utc"], utc=True))
    days = np.asarray((times - _J2000).total_seconds(), dtype=float) / 86400.0
    fractional_day = (times.hour + times.minute / 60.0 + times.second / 3600.0) / 365.2422
    annual_phase = 2.0 * np.pi * ((times.day_of_year.to_numpy() - 1.0) / 365.2422 + fractional_day)
    synodic_phase = 2.0 * np.pi * np.mod(days, _SYNODIC_MONTH_DAYS) / _SYNODIC_MONTH_DAYS
    sidereal_phase = 2.0 * np.pi * np.mod(days, _SIDEREAL_MONTH_DAYS) / _SIDEREAL_MONTH_DAYS
    anomalistic_phase = 2.0 * np.pi * np.mod(days, _ANOMALISTIC_MONTH_DAYS) / _ANOMALISTIC_MONTH_DAYS
    longitude = np.deg2rad(np.asarray(frame["longitude_deg_east"], dtype=float))
    return pd.DataFrame({
        "latitude_deg": np.asarray(frame["latitude_deg"], dtype=float),
        "longitude_sin": np.sin(longitude),
        "longitude_cos": np.cos(longitude),
        "elevation_km": np.asarray(frame["elevation_m"], dtype=float) / 1000.0,
        "annual_sin": np.sin(annual_phase),
        "annual_cos": np.cos(annual_phase),
        "synodic_sin": np.sin(synodic_phase),
        "synodic_cos": np.cos(synodic_phase),
        "sidereal_sin": np.sin(sidereal_phase),
        "sidereal_cos": np.cos(sidereal_phase),
        "anomalistic_sin": np.sin(anomalistic_phase),
        "anomalistic_cos": np.cos(anomalistic_phase),
    }, columns=FEATURE_NAMES)


def make_targets(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return altitude labels and cyclic azimuth labels, in that order."""
    sun_az = np.deg2rad(np.asarray(frame["sun_az_deg"], dtype=float))
    earth_az = np.deg2rad(np.asarray(frame["earth_az_deg"], dtype=float))
    altitudes = frame[["sun_alt_deg", "earth_alt_deg"]].to_numpy(dtype=float)
    azimuth_vectors = np.column_stack([
        np.sin(sun_az), np.cos(sun_az), np.sin(earth_az), np.cos(earth_az),
    ])
    return altitudes, azimuth_vectors
