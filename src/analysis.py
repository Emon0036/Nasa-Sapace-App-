"""
High-level analysis: combine ephemeris + horizon into
"science questions" answers for a (site, date) pair.

Outputs:
- time series DataFrame
- summary statistics (% sunlight, % Earth visible, etc.)
- helper for date sweeps
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd

from . import ephemeris, horizon
from .sites import Site


@dataclass
class Summary:
    site_id: str
    site_name: str
    start_utc: datetime
    end_utc: datetime
    duration_hours: float
    backend: str

    sun_above_horizon_pct: float        # geometric (>0)
    sun_above_real_horizon_pct: float   # legacy name; geometric or processed-DEM mask
    sun_mean_altitude_deg: float
    sun_max_altitude_deg: float

    earth_above_horizon_pct: float
    earth_above_real_horizon_pct: float  # legacy name; geometric or processed-DEM mask
    earth_mean_altitude_deg: float
    earth_min_altitude_deg: float
    earth_max_altitude_deg: float

    sunlit_continuous_hours_max: float
    earth_blackout_minutes: float


def _continuous_runs(mask: np.ndarray, dt_hours: float) -> List[float]:
    """Return contiguous interval durations (in hours), without one-sample overcount."""
    mask = np.asarray(mask, dtype=bool)
    if len(mask) < 2:
        return []
    runs: list[float] = []
    cur_intervals = 0
    for left, right in zip(mask[:-1], mask[1:]):
        if left and right:
            cur_intervals += 1
        elif cur_intervals:
            runs.append(cur_intervals * dt_hours)
            cur_intervals = 0
    if cur_intervals:
        runs.append(cur_intervals * dt_hours)
    return runs


def analyze(site: Site,
            start_utc: datetime,
            duration_hours: float = 24.0 * 5,  # 5 lunar days
            step_minutes: float = 5.0,
            profile: horizon.HorizonProfile | None = None,
            include_dem_mask: bool = True) -> Tuple[pd.DataFrame, Summary]:
    """Compute sky time series and summary stats for a site over a window."""
    if duration_hours <= 0:
        raise ValueError("duration_hours must be greater than zero")
    if step_minutes <= 0:
        raise ValueError("step_minutes must be greater than zero")
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)

    n_steps = int(duration_hours * 60 / step_minutes) + 1
    times = [start_utc + timedelta(minutes=step_minutes * i) for i in range(n_steps)]
    dt_hours = step_minutes / 60.0

    sky = ephemeris.compute_sky(
        times, site.lat_deg, site.lon_deg, site.elev_m, site_id=site.site_id)
    df = pd.DataFrame({
        "time_utc": sky.times_utc,
        "sun_alt_deg": sky.sun_alt,
        "sun_az_deg": sky.sun_az,
        "earth_alt_deg": sky.earth_alt,
        "earth_az_deg": sky.earth_az,
    })

    if include_dem_mask and profile is None:
        profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)

    # Only a processed DEM is evidence for a terrain obstruction mask. The
    # bundled deterministic profiles are visual aids, not measured LOLA data.
    if include_dem_mask and profile is not None and profile.source == "dem":
        # Per-row horizon altitude: where the Sun / Earth must clear the rim
        horizon_sun = np.array([profile.horizon_altitude_at(az) for az in df["sun_az_deg"]])
        horizon_earth = np.array([profile.horizon_altitude_at(az) for az in df["earth_az_deg"]])
        df["sun_horizon_deg"] = horizon_sun
        df["earth_horizon_deg"] = horizon_earth
        df["sun_visible"] = df["sun_alt_deg"] > df["sun_horizon_deg"]
        df["earth_visible"] = df["earth_alt_deg"] > df["earth_horizon_deg"]
    else:
        df["sun_visible"] = df["sun_alt_deg"] > 0
        df["earth_visible"] = df["earth_alt_deg"] > 0

    end_utc = times[-1]
    summary = _summarize(df, site, start_utc, end_utc, dt_hours, sky.backend)
    return df, summary


def _summarize(df: pd.DataFrame, site: Site,
               start_utc: datetime, end_utc: datetime,
               dt_hours: float, backend: str) -> Summary:
    sunlit_geom = (df["sun_alt_deg"] > 0).mean() * 100
    sunlit_real = df["sun_visible"].mean() * 100
    sun_runs = _continuous_runs(df["sun_visible"].values, dt_hours)
    sun_run_max = max(sun_runs) if sun_runs else 0.0

    # Earth blackout: contiguous NOT-visible runs in minutes
    earth_runs = _continuous_runs((~df["earth_visible"]).values, dt_hours)
    earth_blackout_min = max(earth_runs) * 60 if earth_runs else 0.0

    return Summary(
        site_id=site.site_id,
        site_name=site.name,
        start_utc=start_utc,
        end_utc=end_utc,
        duration_hours=(end_utc - start_utc).total_seconds() / 3600.0,
        backend=backend,
        sun_above_horizon_pct=float(sunlit_geom),
        sun_above_real_horizon_pct=float(sunlit_real),
        sun_mean_altitude_deg=float(df["sun_alt_deg"].mean()),
        sun_max_altitude_deg=float(df["sun_alt_deg"].max()),
        earth_above_horizon_pct=float((df["earth_alt_deg"] > 0).mean() * 100),
        earth_above_real_horizon_pct=float(df["earth_visible"].mean() * 100),
        earth_mean_altitude_deg=float(df["earth_alt_deg"].mean()),
        earth_min_altitude_deg=float(df["earth_alt_deg"].min()),
        earth_max_altitude_deg=float(df["earth_alt_deg"].max()),
        sunlit_continuous_hours_max=float(sun_run_max),
        earth_blackout_minutes=float(earth_blackout_min),
    )


def date_sweep(site: Site,
               start_date_utc: datetime,
               n_dates: int = 12,
               duration_hours: float = 24.0,
               step_minutes: float = 15.0,
               stride_days: float = 27.3,
               include_dem_mask: bool = False) -> pd.DataFrame:
    """Sample `n_dates` windows across a year (every ~lunar day) and return
    summary statistics per date. Returns a DataFrame keyed by date."""
    if start_date_utc.tzinfo is None:
        start_date_utc = start_date_utc.replace(tzinfo=timezone.utc)

    rows = []
    cached_site = _cached_ephemeris_for_site(site.site_id)
    for i in range(n_dates):
        t0 = start_date_utc + timedelta(days=stride_days * i)
        cached_window = None
        if cached_site is not None and len(cached_site) >= 2:
            offsets = np.abs((cached_site["time_utc"] - pd.Timestamp(t0)).dt.total_seconds().to_numpy())
            nearest = int(np.argmin(offsets))
            cache_step_hours = float(
                (cached_site["time_utc"].iloc[1] - cached_site["time_utc"].iloc[0]).total_seconds() / 3600.0
            )
            cache_intervals = int(round(duration_hours / cache_step_hours)) if cache_step_hours > 0 else 0
            cached_duration = cache_intervals * cache_step_hours
            duration_matches_cache = cache_intervals >= 1 and abs(cached_duration - duration_hours) < 1e-6
            if duration_matches_cache:
                candidate = cached_site.iloc[nearest:nearest + cache_intervals + 1].copy()
                if len(candidate) == cache_intervals + 1:
                    cached_window = candidate

        if cached_window is not None:
            df = cached_window.rename(columns={
                "sun_alt_deg": "sun_alt_deg", "sun_az_deg": "sun_az_deg",
                "earth_alt_deg": "earth_alt_deg", "earth_az_deg": "earth_az_deg",
            })
            profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m) if include_dem_mask else None
            if profile is not None and profile.source == "dem":
                df["sun_horizon_deg"] = [profile.horizon_altitude_at(a) for a in df["sun_az_deg"]]
                df["earth_horizon_deg"] = [profile.horizon_altitude_at(a) for a in df["earth_az_deg"]]
                df["sun_visible"] = df["sun_alt_deg"] > df["sun_horizon_deg"]
                df["earth_visible"] = df["earth_alt_deg"] > df["earth_horizon_deg"]
            else:
                df["sun_visible"] = df["sun_alt_deg"] > 0
                df["earth_visible"] = df["earth_alt_deg"] > 0
            sample_hours = float((df["time_utc"].iloc[1] - df["time_utc"].iloc[0]).total_seconds() / 3600.0)
            s = _summarize(
                df, site, pd.Timestamp(df["time_utc"].iloc[0]).to_pydatetime(),
                pd.Timestamp(df["time_utc"].iloc[-1]).to_pydatetime(), sample_hours,
                str(df["ephemeris_source"].iloc[0]) if "ephemeris_source" in df else "Horizons cache",
            )
        else:
            df, s = analyze(site, t0, duration_hours=duration_hours,
                            step_minutes=step_minutes,
                            include_dem_mask=include_dem_mask)
        rows.append({
            "date_utc": t0.date().isoformat(),
            "sun_above_real_horizon_pct": s.sun_above_real_horizon_pct,
            "sun_max_altitude_deg": s.sun_max_altitude_deg,
            "sunlit_continuous_hours_max": s.sunlit_continuous_hours_max,
            "earth_above_real_horizon_pct": s.earth_above_real_horizon_pct,
            "earth_min_altitude_deg": s.earth_min_altitude_deg,
            "earth_blackout_minutes": s.earth_blackout_minutes,
        })
    return pd.DataFrame(rows)


@lru_cache(maxsize=4)
def _load_horizons_training_data(path_string: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    frame = pd.read_csv(path_string, parse_dates=["time_utc"])
    frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)
    return frame


def _cached_ephemeris_for_site(site_id: str) -> pd.DataFrame | None:
    path = Path(__file__).resolve().parent.parent / "data" / "processed" / "horizons_ephemeris.csv"
    if not path.exists():
        return None
    frame = _load_horizons_training_data(str(path), path.stat().st_mtime_ns)
    site_frame = frame[frame["site_id"] == site_id].sort_values("time_utc").reset_index(drop=True)
    return site_frame if len(site_frame) else None
