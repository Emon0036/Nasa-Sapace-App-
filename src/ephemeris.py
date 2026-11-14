"""Topocentric Sun and Earth ephemerides for lunar surface sites.

The preferred offline backend is NAIF SPICE with a time-dependent lunar
orientation PCK. When CSPICE is unavailable, the module queries NASA/JPL
Horizons directly for airless topocentric azimuth/elevation. It never treats
an inertial vector as Moon-fixed or silently substitutes an unvalidated model.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd

_SPICE_IMPORT_ERROR: Optional[str] = None
try:
    import spiceypy as spice  # type: ignore
except Exception as exc:  # CSPICE may be blocked or not installed.
    spice = None  # type: ignore[assignment]
    _SPICE_IMPORT_ERROR = str(exc)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


_KERNEL_DIR = _project_root() / "kernels"
_SPICE_FURNISHED = False
_SPICE_FAILURE: Optional[str] = None
_MOON_FRAME = "MOON_ME"
_MOON_RADIUS_KM = 1737.4


def _try_furnish_spice() -> bool:
    """Load a compatible local SPICE kernel set once."""
    global _SPICE_FURNISHED, _SPICE_FAILURE
    if _SPICE_FURNISHED:
        return True
    if os.name == "nt":
        _SPICE_FAILURE = (
            "Local SPICE was not attempted on Windows. Use the Horizons backend here; "
            "run the backend in an approved Linux environment for local CSPICE."
        )
        return False
    if spice is None:
        _SPICE_FAILURE = _SPICE_IMPORT_ERROR or "spiceypy/CSPICE is unavailable"
        return False
    if not _KERNEL_DIR.exists():
        _SPICE_FAILURE = f"No SPICE kernel directory at {_KERNEL_DIR}"
        return False

    # Load constants and frame definitions before binary PCK orientation data.
    suffix_order = (".tls", ".tpc", ".tf", ".bsp", ".bpc")
    kernels = [p for suffix in suffix_order for p in sorted(_KERNEL_DIR.glob(f"*{suffix}"))]
    if not kernels:
        _SPICE_FAILURE = "No SPICE kernels were found"
        return False

    try:
        spice.kclear()
        for kernel in kernels:
            spice.furnsh(str(kernel))
        if spice.namfrm(_MOON_FRAME) == 0:
            raise RuntimeError("The loaded frame kernels do not define MOON_ME")
        # Check that the frame and target states cover the app's reference era.
        et = spice.utc2et("2026 JUN 01 00:00:00 UTC")
        spice.pxform("J2000", _MOON_FRAME, et)
        spice.spkezr("SUN", et, "J2000", "LT+S", "MOON")
        spice.spkezr("EARTH", et, "J2000", "LT+S", "MOON")
        _SPICE_FURNISHED = True
        _SPICE_FAILURE = None
        return True
    except Exception as exc:
        try:
            spice.kclear()
        except Exception:
            pass
        _SPICE_FAILURE = f"SPICE kernels could not be loaded or do not cover the requested epoch: {exc}"
        return False


def using_spice() -> bool:
    """True when CSPICE and compatible planetary/lunar kernels are usable."""
    return _try_furnish_spice()


def backend_status() -> tuple[str, str]:
    """Return a concise backend name and its evidence/availability note."""
    if using_spice():
        return "SPICE · DE440 / MOON_ME", "Local DE440 SPK and lunar orientation PCK loaded."
    return (
        "NASA/JPL Horizons · DE441",
        "Topocentric apparent azimuth/elevation queried from JPL Horizons; results are cached locally.",
    )


def utc_string(t: datetime) -> str:
    """Format an aware or naive datetime as UTC for SPICE."""
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    else:
        t = t.astimezone(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f")


def to_et(t: datetime) -> float:
    if not using_spice():
        raise RuntimeError(_SPICE_FAILURE or "CSPICE is unavailable")
    return float(spice.utc2et(utc_string(t)))


def _site_position_me(site_lat_deg: float, site_lon_deg: float, site_elev_m: float) -> np.ndarray:
    """Observer position in the Moon ME body-fixed frame, in km."""
    lat = math.radians(site_lat_deg)
    lon = math.radians(site_lon_deg)
    radius = _MOON_RADIUS_KM + site_elev_m / 1000.0
    return radius * np.asarray([
        math.cos(lat) * math.cos(lon),
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
    ], dtype=float)


def _enu_basis(site_lat_deg: float, site_lon_deg: float) -> np.ndarray:
    """Rows are geodetic east, north, and up unit vectors in Moon ME."""
    lat = math.radians(site_lat_deg)
    lon = math.radians(site_lon_deg)
    return np.asarray([
        [-math.sin(lon), math.cos(lon), 0.0],
        [-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)],
        [ math.cos(lat) * math.cos(lon),  math.cos(lat) * math.sin(lon), math.sin(lat)],
    ], dtype=float)


def _vector_to_altaz(
    target_from_moon_km: np.ndarray,
    site_lat_deg: float,
    site_lon_deg: float,
    site_elev_m: float = 0.0,
) -> Tuple[float, float]:
    """Convert a Moon-centered position vector to topocentric altitude/azimuth."""
    observer = _site_position_me(site_lat_deg, site_lon_deg, site_elev_m)
    enu = _enu_basis(site_lat_deg, site_lon_deg) @ (np.asarray(target_from_moon_km) - observer)
    east, north, up = (float(v) for v in enu)
    altitude = math.degrees(math.atan2(up, math.hypot(east, north)))
    azimuth = math.degrees(math.atan2(east, north)) % 360.0
    return altitude, azimuth


def topocentric_altaz(
    vec_iau_moon: np.ndarray,
    site_lat_deg: float,
    site_lon_deg: float,
    site_elev_m: float = 0.0,
    et: Optional[float] = None,
) -> Tuple[float, float]:
    """Convert a Moon-centered position vector in ``MOON_ME`` to local alt/az.

    ``et`` is accepted for compatibility with the original API; the input
    vector must already be rotated into the Moon ME frame at that epoch.
    """
    del et
    return _vector_to_altaz(vec_iau_moon, site_lat_deg, site_lon_deg, site_elev_m)


def _to_datetime_index(times: Iterable) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(list(times), utc=True))


def _spice_moon_relative_positions(times: Iterable[datetime]) -> tuple[np.ndarray, np.ndarray]:
    """Return apparent Moon-centered Sun/Earth positions in MOON_ME, km."""
    if not using_spice():
        raise RuntimeError(_SPICE_FAILURE or "SPICE kernels are unavailable")
    times = list(times)
    sun = np.empty((len(times), 3), dtype=float)
    earth = np.empty((len(times), 3), dtype=float)
    for i, t in enumerate(times):
        if isinstance(t, np.datetime64):
            t = pd.Timestamp(t).to_pydatetime()
        et = spice.utc2et(utc_string(t))
        sun_state, _ = spice.spkezr("SUN", et, "J2000", "LT+S", "MOON")
        earth_state, _ = spice.spkezr("EARTH", et, "J2000", "LT+S", "MOON")
        j2000_to_me = np.asarray(spice.pxform("J2000", _MOON_FRAME, et), dtype=float)
        sun[i] = j2000_to_me @ np.asarray(sun_state[:3], dtype=float)
        earth[i] = j2000_to_me @ np.asarray(earth_state[:3], dtype=float)
    return sun, earth


def sun_earth_in_lunar_frame(times_utc: Iterable[datetime]) -> Tuple[np.ndarray, np.ndarray, str]:
    """Return Moon-centered apparent Sun/Earth position vectors in km in ``MOON_ME``.

    This helper intentionally has no analytic fallback: without a time-varying
    lunar frame, an inertial vector is not a Moon-fixed direction.
    """
    if not using_spice():
        raise RuntimeError(_SPICE_FAILURE or "No validated Moon-fixed SPICE frame is available")
    sun, earth = _spice_moon_relative_positions(times_utc)
    return sun, earth, "spice"


@dataclass
class SkyResult:
    """Topocentric sky conditions returned for a sequence of UTC instants."""
    times_utc: pd.DatetimeIndex
    sun_alt: np.ndarray
    sun_az: np.ndarray
    earth_alt: np.ndarray
    earth_az: np.ndarray
    backend: str


def compute_sky(
    times_utc: Iterable[datetime],
    site_lat_deg: float,
    site_lon_deg: float,
    site_elev_m: float = 0.0,
    *,
    site_id: str = "custom",
) -> SkyResult:
    """Compute apparent Sun/Earth alt/az from a lunar surface observer.

    SPICE is used only with a loaded time-dependent lunar orientation kernel.
    Otherwise the NASA/JPL Horizons observer API supplies the same
    topocentric quantities. Network/query errors are returned to the caller;
    there is no silent low-accuracy fallback.
    """
    idx = _to_datetime_index(times_utc)
    if len(idx) == 0:
        empty = np.asarray([], dtype=float)
        return SkyResult(idx, empty, empty, empty, empty, "none")

    if using_spice():
        sun_positions, earth_positions = _spice_moon_relative_positions(idx.to_pydatetime())
        sun_alt = np.empty(len(idx), dtype=float)
        sun_az = np.empty(len(idx), dtype=float)
        earth_alt = np.empty(len(idx), dtype=float)
        earth_az = np.empty(len(idx), dtype=float)
        for i in range(len(idx)):
            sun_alt[i], sun_az[i] = _vector_to_altaz(
                sun_positions[i], site_lat_deg, site_lon_deg, site_elev_m)
            earth_alt[i], earth_az[i] = _vector_to_altaz(
                earth_positions[i], site_lat_deg, site_lon_deg, site_elev_m)
        return SkyResult(idx, sun_alt, sun_az, earth_alt, earth_az, "spice")

    from .horizons import query_site_ephemeris

    data, source = query_site_ephemeris(
        idx, site_lat_deg, site_lon_deg, site_elev_m, site_id=site_id)
    return SkyResult(
        times_utc=idx,
        sun_alt=data["sun_alt_deg"].to_numpy(dtype=float),
        sun_az=data["sun_az_deg"].to_numpy(dtype=float),
        earth_alt=data["earth_alt_deg"].to_numpy(dtype=float),
        earth_az=data["earth_az_deg"].to_numpy(dtype=float),
        backend=source,
    )
