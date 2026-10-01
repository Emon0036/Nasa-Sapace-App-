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
    sun_above_real_horizon_pct: float   # masked by terrain
    sun_mean_altitude_deg: float
    sun_max_altitude_deg: float

    earth_above_horizon_pct: float
    earth_above_real_horizon_pct: float
    earth_mean_altitude_deg: float
    earth_min_altitude_deg: float
    earth_max_altitude_deg: float

    sunlit_continuous_hours_max: float
    earth_blackout_minutes: float
    golden_window_pct: float
    golden_window_continuous_hours_max: float
    sun_min_clearance_deg: float
    earth_min_clearance_deg: float


def _continuous_runs(mask: np.ndarray, dt_hours: float) -> List[float]:
    """Return durations (in hours) of contiguous True runs."""
    runs = []
    cur = 0
    for v in mask:
        if v:
            cur += 1
        else:
            if cur > 0:
                # A run that ends at a sampled false value spans `cur` sample
                # intervals.  The final run is handled below because there is
                # no sample after the requested analysis window to establish
                # another interval.
                runs.append(cur * dt_hours)
                cur = 0
    if cur > 0:
        # Do not report time beyond the requested window.  For example, a
        # 24-hour window sampled every 15 minutes has 97 samples but spans
        # exactly 24 hours, not 24.25 hours.
        runs.append(max(cur - 1, 0) * dt_hours)
    return runs


def golden_windows(df: pd.DataFrame,
                   min_sun_elevation_deg: float = 0.0,
                   min_earth_elevation_deg: float = 0.0) -> pd.DataFrame:
    """Return contiguous periods with simultaneous Sun and Earth access.

    Visibility always uses the terrain-aware boolean columns produced by
    :func:`analyze`. Optional elevation thresholds are applied in addition.
    The returned table contains only windows with UTC start/end and metrics
    computed from the real time series.
    """
    if df.empty:
        return pd.DataFrame(columns=["start_utc", "end_utc", "duration_hours",
                                     "min_sun_elevation_deg",
                                     "min_earth_elevation_deg"])
    mask = (df["sun_visible"].astype(bool)
            & df["earth_visible"].astype(bool)
            & (df["sun_alt_deg"] >= float(min_sun_elevation_deg))
            & (df["earth_alt_deg"] >= float(min_earth_elevation_deg)))
    times = pd.to_datetime(df["time_utc"], utc=True)
    rows = []
    start = None
    for i, active in enumerate(mask.to_numpy()):
        if active and start is None:
            start = i
        if start is not None and (not active or i == len(mask) - 1):
            end = i if active and i == len(mask) - 1 else i - 1
            if end >= start:
                duration_h = (times.iloc[end] - times.iloc[start]).total_seconds() / 3600.0
                rows.append({
                    "start_utc": times.iloc[start],
                    "end_utc": times.iloc[end],
                    "duration_hours": duration_h,
                    "min_sun_elevation_deg": float(df.iloc[start:end + 1]["sun_alt_deg"].min()),
                    "min_earth_elevation_deg": float(df.iloc[start:end + 1]["earth_alt_deg"].min()),
                })
            start = None
    return pd.DataFrame(rows)


def analyze(site: Site,
            start_utc: datetime,
            duration_hours: float = 24.0 * 5,  # 5 lunar days
            step_minutes: float = 5.0,
            profile: horizon.HorizonProfile | None = None,
            include_dem_mask: bool = True) -> Tuple[pd.DataFrame, Summary]:
    """Compute sky time series and summary stats for a site over a window."""
    if duration_hours < 0:
        raise ValueError("duration_hours must be non-negative")
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)

    n_steps = int(duration_hours * 60 / step_minutes) + 1
    times = [start_utc + timedelta(minutes=step_minutes * i) for i in range(n_steps)]
    dt_hours = step_minutes / 60.0

    sky = ephemeris.compute_sky(times, site.lat_deg, site.lon_deg, site.elev_m)
    df = pd.DataFrame({
        "time_utc": sky.times_utc,
        "sun_alt_deg": sky.sun_alt,
        "sun_az_deg": sky.sun_az,
        "earth_alt_deg": sky.earth_alt,
        "earth_az_deg": sky.earth_az,
    })

    if include_dem_mask and profile is None:
        profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)

    if include_dem_mask:
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
    overlap = df["sun_visible"].astype(bool) & df["earth_visible"].astype(bool)
    overlap_runs = _continuous_runs(overlap.values, dt_hours)
    sun_clearance = df["sun_alt_deg"] - df.get("sun_horizon_deg", 0)
    earth_clearance = df["earth_alt_deg"] - df.get("earth_horizon_deg", 0)

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
        golden_window_pct=float(overlap.mean() * 100),
        golden_window_continuous_hours_max=float(max(overlap_runs) if overlap_runs else 0.0),
        sun_min_clearance_deg=float(sun_clearance.min()),
        earth_min_clearance_deg=float(earth_clearance.min()),
    )


def date_sweep(site: Site,
               start_date_utc: datetime,
               n_dates: int = 12,
               duration_hours: float = 24.0,
               step_minutes: float = 15.0,
               stride_days: float = 27.3,
               include_dem_mask: bool = True) -> pd.DataFrame:
    """Sample `n_dates` windows across a year (every ~lunar day) and return
    summary statistics per date. Returns a DataFrame keyed by date."""
    if n_dates < 1:
        raise ValueError("n_dates must be at least 1")
    if duration_hours < 0:
        raise ValueError("duration_hours must be non-negative")
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    if start_date_utc.tzinfo is None:
        start_date_utc = start_date_utc.replace(tzinfo=timezone.utc)

    rows = []
    for i in range(n_dates):
        t0 = start_date_utc + timedelta(days=stride_days * i)
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
