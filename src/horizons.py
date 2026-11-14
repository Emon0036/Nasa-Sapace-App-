"""NASA/JPL Horizons observer API client with a provenance-preserving cache."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "horizons_cache"
MAX_POINTS_PER_QUERY = 5000
REQUEST_TIMEOUT_SECONDS = 45

_DATE_RE = re.compile(
    r"^\s*(\d{4}-[A-Za-z]{3}-\d{2}\s+\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)\s+(.*)$"
)
_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def _as_utc_index(times: Iterable) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(list(times), utc=True))
    if len(index) == 0:
        return index
    if not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError("Horizons times must be strictly increasing and unique")
    return index


def _step_spec(index: pd.DatetimeIndex) -> str:
    if len(index) < 2:
        return "1 m"
    seconds = (index[1] - index[0]).total_seconds()
    if seconds <= 0 or any((index[i] - index[i - 1]).total_seconds() != seconds
                           for i in range(2, len(index))):
        raise ValueError("Horizons queries require a regular time cadence")
    whole_seconds = int(round(seconds))
    if abs(seconds - whole_seconds) > 1e-6:
        raise ValueError("Horizons time cadence must use whole seconds")
    if whole_seconds % 3600 == 0:
        return f"{whole_seconds // 3600} h"
    if whole_seconds % 60 == 0:
        return f"{whole_seconds // 60} m"
    return f"{whole_seconds} s"


def _query_params(
    target_id: str,
    latitude_deg: float,
    longitude_deg: float,
    elevation_m: float,
    start_utc: pd.Timestamp,
    stop_utc: pd.Timestamp,
    step: str,
) -> dict[str, str]:
    # Horizons expects geodetic coordinates as east longitude, latitude,
    # altitude above its lunar ME surface in kilometres.
    site_coord = f"{longitude_deg:.8f},{latitude_deg:.8f},{elevation_m / 1000.0:.6f}"
    return {
        "format": "json",
        "COMMAND": f"'{target_id}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{site_coord}'",
        "START_TIME": f"'{start_utc.strftime('%Y-%m-%d %H:%M:%S')}'",
        "STOP_TIME": f"'{stop_utc.strftime('%Y-%m-%d %H:%M:%S')}'",
        "STEP_SIZE": f"'{step}'",
        "TIME_DIGITS": "'SECONDS'",
        "QUANTITIES": "'4'",  # apparent, airless azimuth/elevation in degrees
    }


def _cache_paths(site_id: str, target_id: str, params: dict[str, str]) -> tuple[Path, Path]:
    normalized_id = re.sub(r"[^A-Za-z0-9_-]+", "_", site_id)[:48] or "site"
    digest = hashlib.sha256(
        json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    stem = f"{normalized_id}_{target_id}_{digest}"
    return RAW_CACHE_DIR / f"{stem}.json", RAW_CACHE_DIR / f"{stem}.meta.json"


def _load_or_query(
    site_id: str,
    target_id: str,
    target_name: str,
    params: dict[str, str],
) -> dict:
    raw_path, meta_path = _cache_paths(site_id, target_id, params)
    if raw_path.exists():
        return json.loads(raw_path.read_text(encoding="utf-8"))

    try:
        url = f"{API_URL}?{urlencode(params)}"
        request = Request(url, headers={
            "User-Agent": "Lunar-Horizon/1.0 (NASA Space Apps research prototype)"})
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_bytes = response.read()
        payload = json.loads(response_bytes)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise RuntimeError(
            f"NASA/JPL Horizons request for {target_name} failed: {exc}. "
            "Check network access or prepare the local Horizons cache first."
        ) from exc

    if payload.get("error"):
        raise RuntimeError(f"NASA/JPL Horizons rejected the {target_name} query: {payload['error']}")
    if not isinstance(payload.get("result"), str):
        raise RuntimeError(f"NASA/JPL Horizons returned no ephemeris text for {target_name}")

    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    metadata = {
        "source_url": API_URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_id": target_id,
        "target_name": target_name,
        "query_parameters": params,
        "response_file": raw_path.name,
        "response_bytes": len(response_bytes),
    }
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    # Be polite to the public API when a site requires Sun and Earth queries.
    time.sleep(0.15)
    return payload


def _parse_rows(payload: dict, target_name: str) -> pd.DataFrame:
    text = payload.get("result", "")
    start = text.find("$$SOE")
    end = text.find("$$EOE", start + 5)
    if start < 0 or end < 0:
        raise RuntimeError(f"NASA/JPL Horizons response for {target_name} has no $$SOE/$$EOE data block")

    rows: list[tuple[pd.Timestamp, float, float]] = []
    for line in text[start + 5:end].splitlines():
        match = _DATE_RE.match(line)
        if not match:
            continue
        numbers = _NUMBER_RE.findall(match.group(2))
        if len(numbers) < 2:
            continue
        stamp_text = " ".join(match.group(1).split())
        stamp = pd.to_datetime(stamp_text, format="mixed", utc=True, errors="coerce")
        if pd.isna(stamp):
            raise RuntimeError(f"Could not parse Horizons timestamp {stamp_text!r}")
        azimuth, altitude = float(numbers[0]), float(numbers[1])
        if not (-360.0 <= azimuth <= 720.0 and -90.5 <= altitude <= 90.5):
            raise RuntimeError(f"Horizons returned implausible azimuth/elevation for {target_name}: {line}")
        rows.append((stamp, azimuth % 360.0, altitude))

    if not rows:
        raise RuntimeError(f"NASA/JPL Horizons returned zero parseable rows for {target_name}")
    data = pd.DataFrame(rows, columns=["time_utc", "az_deg", "alt_deg"])
    data = data.drop_duplicates("time_utc").set_index("time_utc").sort_index()
    if not data.index.is_unique:
        raise RuntimeError(f"NASA/JPL Horizons returned duplicate timestamps for {target_name}")
    return data


def _source_label(*payloads: dict) -> str:
    for payload in payloads:
        match = re.search(r"\{source:\s*([^}]+)\}", payload.get("result", ""), flags=re.IGNORECASE)
        if match:
            return f"JPL Horizons / {match.group(1).strip()}"
    return "JPL Horizons"


def query_site_ephemeris(
    times_utc: Iterable,
    site_lat_deg: float,
    site_lon_deg: float,
    site_elev_m: float = 0.0,
    *,
    site_id: str = "custom",
) -> tuple[pd.DataFrame, str]:
    """Query both targets for a lunar geodetic observer and return aligned rows.

    Horizons quantity 4 is apparent, airless topocentric azimuth/elevation.
    Longitudes are east-positive; site elevation is supplied to the API in km.
    Returned times are UTC and the observer frame is Horizons' high-precision
    lunar mean-Earth reference frame.
    """
    index = _as_utc_index(times_utc)
    if len(index) == 0:
        empty = pd.DataFrame(columns=["sun_alt_deg", "sun_az_deg", "earth_alt_deg", "earth_az_deg"])
        return empty, "none"
    if not -90.0 <= float(site_lat_deg) <= 90.0:
        raise ValueError("Lunar latitude must be between -90 and +90 degrees")
    if not -360.0 <= float(site_lon_deg) <= 360.0:
        raise ValueError("Lunar longitude must be between -360 and +360 degrees")
    if not -12000.0 <= float(site_elev_m) <= 12000.0:
        raise ValueError("Lunar site elevation must be between -12,000 and +12,000 m")
    if len(index) > MAX_POINTS_PER_QUERY:
        raise ValueError(
            f"This request contains {len(index):,} samples; the Horizons client limit is "
            f"{MAX_POINTS_PER_QUERY:,}. Increase the time step or shorten the observation window."
        )

    step = _step_spec(index)
    start, stop = index[0], index[-1]
    targets = (("10", "Sun"), ("399", "Earth"))
    parsed: dict[str, pd.DataFrame] = {}
    payloads: list[dict] = []
    for target_id, target_name in targets:
        params = _query_params(target_id, site_lat_deg, site_lon_deg, site_elev_m, start, stop, step)
        payload = _load_or_query(site_id, target_id, target_name, params)
        payloads.append(payload)
        parsed[target_name] = _parse_rows(payload, target_name)

    result = pd.DataFrame(index=index)
    for target_name, prefix in (("Sun", "sun"), ("Earth", "earth")):
        series = parsed[target_name]
        union_index = series.index.union(index).sort_values()
        aligned = series.reindex(union_index).interpolate(method="time", limit_direction="both").reindex(index)
        if aligned.isna().any().any():
            raise RuntimeError(f"Could not align the Horizons {target_name} rows to all requested times")
        result[f"{prefix}_az_deg"] = aligned["az_deg"].to_numpy(dtype=float)
        result[f"{prefix}_alt_deg"] = aligned["alt_deg"].to_numpy(dtype=float)
    result.index.name = "time_utc"
    return result.reset_index(), _source_label(*payloads)
