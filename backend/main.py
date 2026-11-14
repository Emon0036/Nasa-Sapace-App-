"""REST API for the Lunar Horizon planning interface.

Scientific calculations remain in ``src``. This module validates requests,
calls those existing functions, and converts their results into JSON.
"""

from __future__ import annotations

import importlib.metadata
import json
import logging
import math
import os
import sys
from uuid import UUID
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

try:
    from dotenv import load_dotenv
except ImportError:  # The service still runs when optional local .env support is absent.
    load_dotenv = None  # type: ignore[assignment]

from src import analysis, ephemeris, horizon, recommender, sim
from src.simulator_component import get_simulator_html
from src.sites import SITES, Site, all_sites, get_site
from backend import saved_missions

ROOT = Path(__file__).resolve().parents[1]
if load_dotenv is not None:
    load_dotenv(ROOT / "backend" / ".env", override=False)
logger = logging.getLogger("lunar_horizon.api")


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    status: str
    service: str
    python_version: str
    ephemeris_backend: str
    ephemeris_note: str


class SiteResponse(BaseModel):
    site_id: str
    name: str
    lat_deg: float
    lon_deg: float
    elev_m: float
    description: str
    region: str
    coordinate_note: str
    available_profile_source: str | None = None


class TerrainRegionResponse(BaseModel):
    tile_id: str
    region_name: str
    center_latitude_deg: float
    center_longitude_deg_east: float
    center_elevation_m: float
    resolution_m: float
    bounds_m: dict[str, float]
    coordinate_basis: str
    source_url: str
    recommended_horizon_radius_km: float


class ScienceStatusResponse(BaseModel):
    spice_available: bool
    ephemeris_backend: str
    ephemeris_note: str
    configured_horizon_profiles: dict[str, str]
    measured_dem_available: bool
    ml_model_available: bool
    ml_model_error: str | None
    dataset_provenance: dict[str, Any] | None
    terrain_provenance: dict[str, Any] | None = None
    limitations: list[str]


class SummaryResponse(BaseModel):
    site_id: str
    site_name: str
    start_utc: datetime
    end_utc: datetime
    duration_hours: float
    backend: str
    sun_above_horizon_pct: float
    sun_above_real_horizon_pct: float
    sun_mean_altitude_deg: float
    sun_max_altitude_deg: float
    earth_above_horizon_pct: float
    earth_above_real_horizon_pct: float
    earth_mean_altitude_deg: float
    earth_min_altitude_deg: float
    earth_max_altitude_deg: float
    sunlit_continuous_hours_max: float
    earth_blackout_minutes: float


class EphemerisSampleResponse(BaseModel):
    time_utc: datetime
    sun_alt_deg: float | None
    sun_az_deg: float | None
    earth_alt_deg: float | None
    earth_az_deg: float | None
    sun_horizon_deg: float | None = None
    earth_horizon_deg: float | None = None
    sun_visible: bool
    earth_visible: bool


class HorizonProfileResponse(BaseModel):
    source: str
    site_lat_deg: float
    site_lon_deg: float
    site_elev_m: float
    azimuth_deg: list[float]
    elevation_deg: list[float]
    is_measured_dem: bool
    coverage_range_km: float | None = None
    source_detail: str | None = None
    source_url: str | None = None
    resolution_m: float | None = None


class GoldenWindowResponse(BaseModel):
    start_utc: datetime
    end_utc: datetime
    duration_hours: float
    sample_count: int


class AnalysisProvenanceResponse(BaseModel):
    ephemeris_backend: str
    source_type: str
    horizon_source: str
    display_horizon_source: str | None
    terrain_note: str
    coordinate_note: str
    sampling_note: str


class AnalysisResponse(BaseModel):
    site: SiteResponse
    summary: SummaryResponse
    time_series: list[EphemerisSampleResponse]
    horizon_profile: HorizonProfileResponse | None
    golden_windows: list[GoldenWindowResponse]
    simultaneous_visible_pct: float
    provenance: AnalysisProvenanceResponse


class GoldenWindowsResponse(BaseModel):
    site: SiteResponse
    summary: SummaryResponse
    simultaneous_visible_pct: float
    windows: list[GoldenWindowResponse]
    provenance: AnalysisProvenanceResponse


class ComparisonResponse(BaseModel):
    scenario_a: AnalysisResponse
    scenario_b: AnalysisResponse
    scenario_b_minus_a: dict[str, float]


class SeasonalSampleResponse(BaseModel):
    date_utc: str
    sun_above_real_horizon_pct: float
    sun_max_altitude_deg: float
    sunlit_continuous_hours_max: float
    earth_above_real_horizon_pct: float
    earth_min_altitude_deg: float
    earth_blackout_minutes: float


class SeasonalSiteResponse(BaseModel):
    site: SiteResponse
    horizon_source: str
    display_horizon_source: str
    samples: list[SeasonalSampleResponse]


class SeasonalProvenanceResponse(BaseModel):
    source: str
    terrain_note: str
    sampling_note: str


class SeasonalSweepResponse(BaseModel):
    sites: list[SeasonalSiteResponse]
    start_utc: datetime
    stride_days: float
    provenance: SeasonalProvenanceResponse


class MissionPhaseResponse(BaseModel):
    name: str
    start_seconds: float
    end_seconds: float
    illustrative: bool


class SurfaceTelemetryResponse(EphemerisSampleResponse):
    mission_seconds: float
    phase: str


class MissionProvenanceResponse(BaseModel):
    ephemeris_backend: str
    surface_data: str
    illustration_note: str
    horizon_note: str


class MissionPlanResponse(BaseModel):
    site: SiteResponse
    launch_utc: datetime
    landing_utc: datetime
    duration_seconds: float
    phases: list[MissionPhaseResponse]
    surface_telemetry: list[SurfaceTelemetryResponse]
    horizon_profile: HorizonProfileResponse
    provenance: MissionProvenanceResponse
    simulator_html: str


class ModelMetricsResponse(BaseModel):
    available: bool
    error: str | None
    metrics: dict[str, Any] | None


class MLPredictionResponse(BaseModel):
    candidates: list[dict[str, Any]]
    excluded_sites: list[str]
    metrics: dict[str, Any] | None
    interpretation: str


class PhysicalCheckResponse(BaseModel):
    ml_candidate: dict[str, Any]
    summary: SummaryResponse
    physical_score: float
    simultaneous_visible_pct: float
    horizon_source: str
    terrain_note: str


class RecommendationResponse(BaseModel):
    ml_candidates: list[dict[str, Any]]
    excluded_sites: list[str]
    physical_checks: list[PhysicalCheckResponse]
    recommended: PhysicalCheckResponse | None
    score_definition: str
    metrics: dict[str, Any] | None
    limitations: list[str]


class ScenarioRequest(RequestModel):
    site_id: str = Field(min_length=1, max_length=80)
    start_utc: datetime
    duration_hours: float = Field(default=120.0, gt=0.0, le=240.0)
    step_minutes: float = Field(default=15.0, ge=1.0, le=60.0)
    include_terrain: bool = False
    site_name: str | None = Field(default=None, max_length=120)
    lat_deg: float | None = Field(default=None, ge=-90.0, le=90.0)
    lon_deg: float | None = Field(default=None, ge=-180.0, le=360.0)
    elev_m: float | None = Field(default=None, ge=-12000.0, le=12000.0)

    @field_validator("start_utc")
    @classmethod
    def normalize_start_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def enforce_sample_limit(self) -> "ScenarioRequest":
        sample_count = math.floor(self.duration_hours * 60.0 / self.step_minutes) + 1
        if sample_count > 5000:
            raise ValueError("This cadence creates more than 5,000 samples; increase step_minutes or shorten duration_hours")
        if self.site_id not in SITES and (self.lat_deg is None or self.lon_deg is None):
            raise ValueError("Unknown site_id. Custom sites must include lat_deg and lon_deg")
        return self


class CompareRequest(RequestModel):
    scenario_a: ScenarioRequest
    scenario_b: ScenarioRequest


class SeasonalSweepRequest(RequestModel):
    site_ids: list[str] = Field(min_length=1, max_length=10)
    start_utc: datetime
    n_dates: int = Field(default=12, ge=4, le=24)
    duration_hours: float = Field(default=24.0, gt=0.0, le=240.0)
    step_minutes: float = Field(default=15.0, ge=5.0, le=60.0)
    include_terrain: bool = False

    @field_validator("start_utc")
    @classmethod
    def normalize_start_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SimulationRequest(RequestModel):
    site_id: str
    launch_utc: datetime
    transit_days: float = Field(default=3.0, ge=1.0, le=7.0)
    surface_days: float = Field(default=5.0, ge=1.0, le=10.0)
    step_minutes: float = Field(default=15.0, ge=5.0, le=60.0)

    @field_validator("launch_utc")
    @classmethod
    def normalize_launch_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def enforce_sample_limit(self) -> "SimulationRequest":
        sample_count = math.floor(self.surface_days * 24.0 * 60.0 / self.step_minutes) + 1
        if sample_count > 3000:
            raise ValueError("Surface sampling is limited to 3,000 points; increase step_minutes or shorten surface_days")
        return self


class SavedMissionProfileRequest(RequestModel):
    owner_id: UUID
    name: str = Field(min_length=1, max_length=100)
    site_id: str = Field(min_length=1, max_length=80)
    site_name: str = Field(min_length=1, max_length=120)
    launch_utc: datetime
    transit_days: float = Field(ge=1.0, le=7.0)
    surface_days: float = Field(ge=1.0, le=10.0)
    step_minutes: float = Field(ge=5.0, le=60.0)

    @field_validator("launch_utc")
    @classmethod
    def normalize_launch_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_validator("site_id")
    @classmethod
    def known_site_only(cls, value: str) -> str:
        if value not in SITES:
            raise ValueError("Saved mission profiles must use a listed landing site")
        return value


class SavedMissionProfileResponse(BaseModel):
    id: UUID
    name: str
    site_id: str
    site_name: str
    launch_utc: datetime
    transit_days: float
    surface_days: float
    step_minutes: float
    created_at: datetime


class SavedMissionStoreStatusResponse(BaseModel):
    configured: bool


class MLPredictRequest(RequestModel):
    site_ids: list[str] = Field(min_length=1, max_length=10)
    start_utc: datetime
    duration_hours: float = Field(default=120.0, gt=0.0, le=240.0)
    sample_hours: float = Field(default=3.0, ge=0.25, le=24.0)

    @field_validator("start_utc")
    @classmethod
    def normalize_start_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class RecommendRequest(MLPredictRequest):
    step_minutes: float = Field(default=15.0, ge=1.0, le=60.0)
    include_terrain: bool = True

    @model_validator(mode="after")
    def enforce_physical_sample_limit(self) -> "RecommendRequest":
        sample_count = math.floor(self.duration_hours * 60.0 / self.step_minutes) + 1
        if sample_count > 5000:
            raise ValueError("Physical verification is limited to 5,000 samples; increase step_minutes or shorten duration_hours")
        return self


def _json_safe(value: Any) -> Any:
    """Convert scientific Python values into strict JSON-compatible values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


def _resolve_site(request: ScenarioRequest) -> Site:
    if request.site_id in SITES:
        return get_site(request.site_id)
    assert request.lat_deg is not None and request.lon_deg is not None
    return Site(
        site_id=request.site_id,
        name=request.site_name or f"Custom site ({request.lat_deg:.3f}, {request.lon_deg:.3f})",
        lat_deg=float(request.lat_deg),
        lon_deg=float(request.lon_deg),
        elev_m=float(request.elev_m or 0.0),
        description="User-supplied coordinates; not survey-verified.",
        region="custom",
    )


def _site_payload(site: Site) -> dict[str, Any]:
    return {
        "site_id": site.site_id,
        "name": site.name,
        "lat_deg": site.lat_deg,
        "lon_deg": site.lon_deg,
        "elev_m": site.elev_m,
        "description": site.description,
        "region": site.region,
        "coordinate_note": "Nominal prototype coordinates; not survey-verified landing locations.",
    }


def _profile_payload(profile: horizon.HorizonProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "source": profile.source,
        "site_lat_deg": profile.site_lat_deg,
        "site_lon_deg": profile.site_lon_deg,
        "site_elev_m": profile.site_elev_m,
        "azimuth_deg": profile.azimuth_deg,
        "elevation_deg": profile.elevation_deg,
        "is_measured_dem": profile.source == "dem",
        "coverage_range_km": profile.coverage_range_km,
        "source_detail": profile.source_detail,
        "source_url": profile.source_url,
        "resolution_m": profile.resolution_m,
    }


def _joint_windows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    visible = (frame["sun_visible"].to_numpy(dtype=bool)
               & frame["earth_visible"].to_numpy(dtype=bool))
    times = pd.to_datetime(frame["time_utc"], utc=True).reset_index(drop=True)
    windows: list[dict[str, Any]] = []
    start: int | None = None
    for index, is_visible in enumerate(visible):
        if is_visible and start is None:
            start = index
        at_end = index == len(visible) - 1
        if start is not None and (not is_visible or at_end):
            last_visible = index if is_visible and at_end else index - 1
            window_start = times.iloc[start]
            window_end = times.iloc[last_visible]
            windows.append({
                "start_utc": window_start.isoformat(),
                "end_utc": window_end.isoformat(),
                "duration_hours": (window_end - window_start).total_seconds() / 3600.0,
                "sample_count": last_visible - start + 1,
            })
            start = None
    return windows


def _analyze(request: ScenarioRequest) -> tuple[dict[str, Any], pd.DataFrame, Site, horizon.HorizonProfile | None]:
    site = _resolve_site(request)
    profile = (
        horizon.horizon_for_site(
            site.site_id,
            site.lat_deg,
            site.lon_deg,
            site.elev_m,
            generate_from_tiles=True,
        )
        if request.include_terrain else None
    )
    measured_profile = profile if profile is not None and profile.source == "dem" else None
    frame, summary = analysis.analyze(
        site,
        request.start_utc,
        duration_hours=request.duration_hours,
        step_minutes=request.step_minutes,
        profile=measured_profile,
        include_dem_mask=measured_profile is not None,
    )
    source_note = (
        (
            f"LOLA-derived terrain mask applied within {profile.coverage_range_km:g} km; "
            "the 5 m/pixel elevation grid is interpolated."
            if profile.coverage_range_km is not None and profile.resolution_m is not None
            else "Terrain-adjusted using a processed lunar DEM."
        )
        if profile is not None and profile.source == "dem"
        else "Synthetic horizon profile is illustrative and not applied; geometric visibility is used."
        if profile is not None and profile.source == "synthetic"
        else "Geometric horizon only; no measured DEM mask is applied."
    )
    payload = {
        "site": _site_payload(site),
        "summary": asdict(summary),
        "time_series": frame.to_dict(orient="records"),
        "horizon_profile": _profile_payload(profile),
        "golden_windows": _joint_windows(frame),
        "simultaneous_visible_pct": float(
            (frame["sun_visible"] & frame["earth_visible"]).mean() * 100.0
        ) if len(frame) else 0.0,
        "provenance": {
            "ephemeris_backend": summary.backend,
            "source_type": "NASA/JPL Horizons calculation or local NAIF SPICE calculation",
            "horizon_source": measured_profile.source if measured_profile is not None else "geometric",
            "display_horizon_source": profile.source if profile is not None else None,
            "terrain_note": source_note,
            "coordinate_note": "Nominal prototype coordinates; not survey-verified landing locations.",
            "sampling_note": "Visibility windows are resolved at the requested sampling cadence; threshold crossings are not interpolated.",
        },
    }
    return _json_safe(payload), frame, site, profile


def _raise_science_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, (HTTPError, URLError, TimeoutError, ConnectionError, OSError)):
        logger.warning("Scientific data request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Ephemeris/data request failed: {exc}") from exc
    logger.exception("Scientific calculation failed")
    raise HTTPException(status_code=500, detail=f"Scientific calculation failed: {exc}") from exc


def _configured_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]


app = FastAPI(
    title="Lunar Horizon API",
    description="NASA/JPL Horizons and NAIF SPICE lunar surface visibility analysis.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> dict[str, Any]:
    try:
        backend_name, backend_note = ephemeris.backend_status()
    except Exception as exc:  # Health should still explain partial service availability.
        backend_name, backend_note = "unavailable", str(exc)
    return {
        "status": "ok",
        "service": "Lunar Horizon API",
        "python_version": sys.version.split()[0],
        "ephemeris_backend": backend_name,
        "ephemeris_note": backend_note,
    }


@app.get("/api/sites", response_model=list[SiteResponse])
def sites() -> list[dict[str, Any]]:
    output = []
    for site in all_sites():
        profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
        output.append({**_site_payload(site), "available_profile_source": profile.source})
    return output


@app.get("/api/terrain/regions", response_model=list[TerrainRegionResponse])
def terrain_regions() -> list[dict[str, Any]]:
    manifest_path = ROOT / "data" / "terrain" / "lola" / "provenance.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read LOLA terrain region metadata: %s", exc)
        return []
    return [
        {
            "tile_id": tile["tile_id"],
            "region_name": tile["region_name"],
            "center_latitude_deg": tile["center_latitude_deg"],
            "center_longitude_deg_east": tile["center_longitude_deg_east"],
            "center_elevation_m": tile["center_elevation_m"],
            "resolution_m": tile["resolution_m"],
            "bounds_m": tile["bounds_m"],
            "coordinate_basis": tile["coordinate_basis"],
            "source_url": tile["url"],
            "recommended_horizon_radius_km": 5.0,
        }
        for tile in manifest.get("tiles", [])
    ]


@app.get("/api/science/status", response_model=ScienceStatusResponse)
def science_status() -> dict[str, Any]:
    try:
        spice_available = bool(ephemeris.using_spice())
        backend_name, backend_note = ephemeris.backend_status()
    except Exception as exc:
        spice_available = False
        backend_name, backend_note = "NASA/JPL Horizons · DE441", f"SPICE unavailable: {exc}"

    profile_sources = {
        site.site_id: horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m).source
        for site in all_sites()
    }
    manifest_path = ROOT / "data" / "processed" / "horizons_ephemeris.provenance.json"
    terrain_manifest_path = ROOT / "data" / "terrain" / "lola" / "provenance.json"
    manifest: dict[str, Any] | None = None
    terrain_manifest: dict[str, Any] | None = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read data provenance manifest: %s", exc)
    if terrain_manifest_path.exists():
        try:
            terrain_manifest = json.loads(terrain_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read LOLA terrain provenance: %s", exc)
    try:
        recommender.load_model()
        model_available, model_error = True, None
    except Exception as exc:
        model_available, model_error = False, str(exc)
    return _json_safe({
        "spice_available": spice_available,
        "ephemeris_backend": backend_name,
        "ephemeris_note": backend_note,
        "configured_horizon_profiles": profile_sources,
        "measured_dem_available": any(source == "dem" for source in profile_sources.values()),
        "ml_model_available": model_available,
        "ml_model_error": model_error,
        "dataset_provenance": manifest,
        "terrain_provenance": terrain_manifest,
        "limitations": [
            "Candidate coordinates are nominal prototype points, not surveyed landing zones.",
            "LOLA terrain masks are applied only where a bundled regional DEM fully covers the reported horizon radius; other locations use geometric visibility.",
            "LOLA 5 m/pixel regional elevation products are interpolated grids, not independent measurements at every pixel.",
            "Horizons-derived labels are calculations, not spacecraft observations.",
            "This research prototype is not flight-certified and does not model link budgets or landing hazards.",
        ],
    })


@app.post("/api/analyze", response_model=AnalysisResponse)
def analyze_site(request: ScenarioRequest) -> dict[str, Any]:
    try:
        payload, _, _, _ = _analyze(request)
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        _raise_science_error(exc)


@app.post("/api/golden-windows", response_model=GoldenWindowsResponse)
def golden_windows(request: ScenarioRequest) -> dict[str, Any]:
    try:
        payload, _, _, _ = _analyze(request)
        return {
            "site": payload["site"],
            "summary": payload["summary"],
            "simultaneous_visible_pct": payload["simultaneous_visible_pct"],
            "windows": payload["golden_windows"],
            "provenance": payload["provenance"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        _raise_science_error(exc)


@app.post("/api/compare", response_model=ComparisonResponse)
def compare_scenarios(request: CompareRequest) -> dict[str, Any]:
    try:
        first, _, _, _ = _analyze(request.scenario_a)
        second, _, _, _ = _analyze(request.scenario_b)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_science_error(exc)
    metrics = (
        "sun_above_real_horizon_pct",
        "earth_above_real_horizon_pct",
        "sunlit_continuous_hours_max",
        "earth_blackout_minutes",
        "sun_max_altitude_deg",
        "earth_max_altitude_deg",
    )
    deltas = {
        key: float(second["summary"][key] - first["summary"][key])
        for key in metrics
    }
    deltas["simultaneous_visible_pct"] = float(
        second["simultaneous_visible_pct"] - first["simultaneous_visible_pct"]
    )
    return {"scenario_a": first, "scenario_b": second, "scenario_b_minus_a": deltas}


@app.post("/api/seasonal-sweep", response_model=SeasonalSweepResponse)
def seasonal_sweep(request: SeasonalSweepRequest) -> dict[str, Any]:
    try:
        output = []
        for site_id in request.site_ids:
            site = get_site(site_id)
            values = analysis.date_sweep(
                site,
                request.start_utc,
                n_dates=request.n_dates,
                duration_hours=request.duration_hours,
                step_minutes=request.step_minutes,
                include_dem_mask=request.include_terrain,
            )
            profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
            output.append({
                "site": _site_payload(site),
                "horizon_source": profile.source if request.include_terrain and profile.source == "dem" else "geometric",
                "display_horizon_source": profile.source,
                "samples": values.to_dict(orient="records"),
            })
        return _json_safe({
            "sites": output,
            "start_utc": request.start_utc,
            "stride_days": 27.3,
            "provenance": {
                "source": "Cached six-hour JPL Horizons dataset where covered; direct Horizons analysis otherwise.",
            "terrain_note": "LOLA-derived terrain is applied where a bundled tile covers the site and complete ray radius; other sites use geometric visibility. Synthetic profiles remain display-only.",
                "sampling_note": "Date samples are about 27.3 days apart; each summary uses the existing analysis engine.",
            },
        })
    except Exception as exc:
        _raise_science_error(exc)


@app.post("/api/simulation/plan", response_model=MissionPlanResponse)
def simulation_plan(request: SimulationRequest) -> dict[str, Any]:
    try:
        site = get_site(request.site_id)
        plan = sim.plan_mission(
            site,
            request.launch_utc,
            transit_days=request.transit_days,
            surface_days=request.surface_days,
            step_minutes=request.step_minutes,
        )
        phases = [
            ("LAUNCH", 0.0, plan.launch_seconds, True),
            ("TRANSIT", plan.launch_seconds, plan.launch_seconds + plan.transit_seconds, True),
            ("LUNAR ORBIT", plan.launch_seconds + plan.transit_seconds,
             plan.launch_seconds + plan.transit_seconds + plan.orbit_seconds, True),
            ("POWERED DESCENT", plan.launch_seconds + plan.transit_seconds + plan.orbit_seconds,
             plan.launch_seconds + plan.transit_seconds + plan.orbit_seconds + plan.descent_seconds, True),
            ("SURFACE OPS", plan.total_seconds - plan.surface_seconds, plan.total_seconds, False),
        ]
        earth_horizon = np.asarray([
            plan.profile.horizon_altitude_at(az) for az in plan.surface_earth_az
        ], dtype=float)
        simulator_data = {
            "site": {
                "name": site.name,
                "lat": site.lat_deg,
                "lon": site.lon_deg,
                "elev_m": site.elev_m,
            },
            "launch_utc": plan.launch_utc.isoformat(),
            "launch_seconds": plan.launch_seconds,
            "transit_seconds": plan.transit_seconds,
            "orbit_seconds": plan.orbit_seconds,
            "descent_seconds": plan.descent_seconds,
            "surface_seconds": plan.surface_seconds,
            "total_seconds": plan.total_seconds,
            "horizon_profile": {
                "azimuth_deg": plan.profile.azimuth_deg.tolist(),
                "elevation_deg": plan.profile.elevation_deg.tolist(),
            },
            "surface": {
                "times": [value.isoformat() for value in plan.surface_times],
                "sun_alt": plan.surface_sun_alt.tolist(),
                "sun_az": plan.surface_sun_az.tolist(),
                "earth_alt": plan.surface_earth_alt.tolist(),
                "earth_az": plan.surface_earth_az.tolist(),
                "horizon_sun": plan.horizon_at.tolist(),
                "horizon_earth": earth_horizon.tolist(),
            },
        }
        simulator_html = get_simulator_html(simulator_data)
        telemetry = []
        for index, surface_time in enumerate(plan.surface_times):
            mission_seconds = plan.total_seconds - plan.surface_seconds + index * request.step_minutes * 60.0
            telemetry.append({
                "time_utc": surface_time,
                "mission_seconds": mission_seconds,
                "phase": "SURFACE OPS",
                "sun_alt_deg": plan.surface_sun_alt[index],
                "sun_az_deg": plan.surface_sun_az[index],
                "earth_alt_deg": plan.surface_earth_alt[index],
                "earth_az_deg": plan.surface_earth_az[index],
                "sun_horizon_deg": plan.horizon_at[index],
                "earth_horizon_deg": earth_horizon[index],
                "sun_visible": bool(plan.surface_sun_alt[index] > plan.horizon_at[index]),
                "earth_visible": bool(plan.surface_earth_alt[index] > earth_horizon[index]),
            })
        return _json_safe({
            "site": _site_payload(site),
            "launch_utc": plan.launch_utc,
            "landing_utc": plan.surface_times[0],
            "duration_seconds": plan.total_seconds,
            "phases": [
                {"name": name, "start_seconds": start, "end_seconds": end,
                 "illustrative": illustrative}
                for name, start, end, illustrative in phases
            ],
            "surface_telemetry": telemetry,
            "horizon_profile": _profile_payload(plan.profile),
            "simulator_html": simulator_html,
            "provenance": {
                "ephemeris_backend": ephemeris.backend_status()[0],
                "surface_data": "Computed by src.sim.plan_mission; surface Sun/Earth telemetry uses the configured ephemeris backend.",
                "illustration_note": "Launch, transit, lunar-orbit, and descent scene geometry is illustrative; only the surface sky telemetry is calculated for this site and time.",
                "horizon_note": (
                    f"LOLA-derived terrain profile applied within {plan.profile.coverage_range_km:g} km; "
                    "the elevation grid is interpolated."
                    if plan.profile.source == "dem" and plan.profile.coverage_range_km is not None
                    else "Terrain-adjusted using a processed lunar DEM."
                    if plan.profile.source == "dem"
                    else "Geometric horizon used; synthetic profiles are not applied to visibility."
                ),
            },
        })
    except Exception as exc:
        _raise_science_error(exc)


@app.get("/api/saved-missions", response_model=list[SavedMissionProfileResponse])
def list_saved_missions(owner_id: UUID = Query(...)) -> list[dict[str, Any]]:
    try:
        return saved_missions.list_profiles(owner_id)
    except saved_missions.StoreUnavailable as exc:
        raise HTTPException(status_code=503, detail="Cloud mission storage is unavailable.") from exc


@app.get("/api/saved-missions/status", response_model=SavedMissionStoreStatusResponse)
def saved_mission_store_status() -> dict[str, bool]:
    return {"configured": bool(os.getenv("DATABASE_URL"))}


@app.post("/api/saved-missions", response_model=SavedMissionProfileResponse, status_code=201)
def create_saved_mission(request: SavedMissionProfileRequest) -> dict[str, Any]:
    try:
        profile = request.model_dump(exclude={"owner_id"})
        return saved_missions.create_profile(request.owner_id, profile)
    except saved_missions.StoreUnavailable as exc:
        raise HTTPException(status_code=503, detail="Cloud mission storage is unavailable.") from exc


@app.delete("/api/saved-missions/{profile_id}", status_code=204)
def delete_saved_mission(profile_id: UUID, owner_id: UUID = Query(...)) -> Response:
    try:
        deleted = saved_missions.delete_profile(owner_id, profile_id)
    except saved_missions.StoreUnavailable as exc:
        raise HTTPException(status_code=503, detail="Cloud mission storage is unavailable.") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved mission profile not found.")
    return Response(status_code=204)


@lru_cache(maxsize=1)
def _saved_metrics() -> dict[str, Any] | None:
    path = ROOT / "ml" / "metrics.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@app.get("/api/ml/metrics", response_model=ModelMetricsResponse)
def ml_metrics() -> dict[str, Any]:
    metrics = _saved_metrics()
    try:
        recommender.load_model()
        available, error = True, None
    except Exception as exc:
        available, error = False, str(exc)
    return _json_safe({"available": available, "error": error, "metrics": metrics})


def _rank_request(request: MLPredictRequest) -> tuple[pd.DataFrame, list[Site]]:
    site_objects = [get_site(site_id) for site_id in request.site_ids]
    profiles = {
        site.site_id: horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
        for site in site_objects
    }
    ranked = recommender.rank_scenarios(
        site_objects,
        request.start_utc,
        duration_hours=request.duration_hours,
        profiles=profiles,
        sample_hours=request.sample_hours,
    )
    return ranked, site_objects


@app.post("/api/ml/predict", response_model=MLPredictionResponse)
def ml_predict(request: MLPredictRequest) -> dict[str, Any]:
    try:
        ranked, _ = _rank_request(request)
        return _json_safe({
            "candidates": ranked.to_dict(orient="records"),
            "excluded_sites": ranked.attrs.get("excluded_sites", []),
            "metrics": _saved_metrics(),
            "interpretation": "Surrogate estimates are restricted to model date and coordinate coverage. They are not physical verification.",
        })
    except Exception as exc:
        _raise_science_error(exc)


@app.post("/api/recommend", response_model=RecommendationResponse)
def recommend(request: RecommendRequest) -> dict[str, Any]:
    try:
        ranked, site_objects = _rank_request(request)
        site_by_id = {site.site_id: site for site in site_objects}
        physical_checks = []
        for candidate in ranked.head(3).to_dict(orient="records"):
            site = site_by_id[candidate["site_id"]]
            profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
            use_measured_dem = request.include_terrain and profile.source == "dem"
            frame, summary = analysis.analyze(
                site,
                datetime.fromisoformat(candidate["start_utc"]),
                duration_hours=request.duration_hours,
                step_minutes=request.step_minutes,
                profile=profile if use_measured_dem else None,
                include_dem_mask=use_measured_dem,
            )
            physical_score = (
                recommender.MISSION_SCORE_WEIGHTS["sunlight"] * summary.sun_above_real_horizon_pct
                + recommender.MISSION_SCORE_WEIGHTS["earth_visibility"] * summary.earth_above_real_horizon_pct
            )
            physical_checks.append({
                "ml_candidate": candidate,
                "summary": asdict(summary),
                "physical_score": float(physical_score),
                "simultaneous_visible_pct": float((frame["sun_visible"] & frame["earth_visible"]).mean() * 100.0),
                "horizon_source": profile.source if use_measured_dem else "geometric",
                "terrain_note": (
                    f"LOLA-derived DEM applied within {profile.coverage_range_km:g} km; "
                    "the 5 m/pixel elevation grid is interpolated."
                    if use_measured_dem and profile.coverage_range_km is not None
                    else "Terrain-adjusted with processed DEM."
                    if use_measured_dem
                    else "Synthetic terrain excluded; geometric horizon used."
                ),
            })
        physical_checks.sort(key=lambda item: item["physical_score"], reverse=True)
        return _json_safe({
            "ml_candidates": ranked.to_dict(orient="records"),
            "excluded_sites": ranked.attrs.get("excluded_sites", []),
            "physical_checks": physical_checks,
            "recommended": physical_checks[0] if physical_checks else None,
            "score_definition": "60% physically checked Sun visibility + 40% physically checked Earth visibility, among the top three ML candidates.",
            "metrics": _saved_metrics(),
            "limitations": [
                "The model is an interpolation surrogate within its saved date and coordinate coverage.",
                "The physical re-ranking depends on Horizons/SPICE availability and the requested sample cadence.",
            ],
        })
    except Exception as exc:
        _raise_science_error(exc)
