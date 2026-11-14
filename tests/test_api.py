"""FastAPI contract tests using deterministic, mocked ephemeris output."""

from __future__ import annotations

import unittest
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import numpy as np
import pandas as pd

from backend import saved_missions
from backend.main import app
from src import ephemeris, recommender
from src.analysis import Summary
from src.sites import get_site


class ApiContractTests(unittest.TestCase):
    def request(self, method: str, path: str, *, json: dict | None = None) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, json=json)

        return asyncio.run(send())

    def _fixture(self, site_id: str = "flat_reference", sun_percent: float = 50.0):
        site = get_site(site_id)
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        times = pd.date_range(start, periods=3, freq="1h")
        frame = pd.DataFrame({
            "time_utc": times,
            "sun_alt_deg": np.array([5.0, 6.0, float("nan")]),
            "sun_az_deg": [20.0, 25.0, 30.0],
            "earth_alt_deg": [10.0, 11.0, 12.0],
            "earth_az_deg": [100.0, 110.0, 120.0],
            "sun_visible": [True, True, False],
            "earth_visible": [True, True, True],
        })
        summary = Summary(
            site_id=site.site_id,
            site_name=site.name,
            start_utc=start,
            end_utc=times[-1].to_pydatetime(),
            duration_hours=2.0,
            backend="JPL Horizons test fixture",
            sun_above_horizon_pct=sun_percent,
            sun_above_real_horizon_pct=sun_percent,
            sun_mean_altitude_deg=5.0,
            sun_max_altitude_deg=6.0,
            earth_above_horizon_pct=100.0,
            earth_above_real_horizon_pct=100.0,
            earth_mean_altitude_deg=11.0,
            earth_min_altitude_deg=10.0,
            earth_max_altitude_deg=12.0,
            sunlit_continuous_hours_max=1.0,
            earth_blackout_minutes=0.0,
        )
        return frame, summary

    def test_health_and_site_catalog(self) -> None:
        health = self.request("GET", "/api/health")
        catalog = self.request("GET", "/api/sites")
        science = self.request("GET", "/api/science/status")
        terrain_regions = self.request("GET", "/api/terrain/regions")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn("shackleton_henson", {item["site_id"] for item in catalog.json()})
        self.assertEqual(science.status_code, 200)
        self.assertEqual(science.json()["terrain_provenance"]["source_dataset_doi"], "10.17189/1520642")
        self.assertEqual(terrain_regions.status_code, 200)
        self.assertEqual(len(terrain_regions.json()), 4)
        self.assertIn("terrain-data sample", terrain_regions.json()[0]["coordinate_basis"])

    def test_saved_mission_profiles_are_scoped_and_returned_by_sql_repository(self) -> None:
        owner_id = uuid4()
        profile_id = uuid4()
        created = {
            "id": profile_id,
            "name": "Shackleton · 2026-09-01",
            "site_id": "shackleton_henson",
            "site_name": "Shackleton-Henson Connecting Ridge",
            "launch_utc": datetime(2026, 9, 1, tzinfo=timezone.utc),
            "transit_days": 3.0,
            "surface_days": 5.0,
            "step_minutes": 15.0,
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        }
        request_body = {
            "owner_id": str(owner_id),
            "name": created["name"],
            "site_id": created["site_id"],
            "site_name": created["site_name"],
            "launch_utc": "2026-09-01T00:00:00Z",
            "transit_days": 3,
            "surface_days": 5,
            "step_minutes": 15,
        }
        with patch("backend.main.saved_missions.create_profile", return_value=created) as create:
            response = self.request("POST", "/api/saved-missions", json=request_body)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["id"], str(profile_id))
        self.assertEqual(response.json()["launch_utc"], "2026-09-01T00:00:00Z")
        create.assert_called_once()

        with patch("backend.main.saved_missions.list_profiles", return_value=[created]):
            listed = self.request("GET", f"/api/saved-missions?owner_id={owner_id}")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

        with patch("backend.main.saved_missions.delete_profile", return_value=True) as delete:
            removed = self.request("DELETE", f"/api/saved-missions/{profile_id}?owner_id={owner_id}")
        self.assertEqual(removed.status_code, 204)
        delete.assert_called_once_with(owner_id, profile_id)

    def test_saved_mission_profiles_report_unconfigured_sql_store(self) -> None:
        owner_id = uuid4()
        with patch("backend.main.saved_missions.list_profiles", side_effect=saved_missions.StoreUnavailable):
            response = self.request("GET", f"/api/saved-missions?owner_id={owner_id}")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Cloud mission storage", response.json()["detail"])

    def test_saved_mission_store_status_does_not_require_database_to_be_configured(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            with patch("backend.main.os.getenv", return_value=None):
                response = self.request("GET", "/api/saved-missions/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"configured": False})

    def test_analyze_serializes_samples_and_joint_windows(self) -> None:
        with patch("backend.main.analysis.analyze", return_value=self._fixture()):
            response = self.request("POST", "/api/analyze", json={
                "site_id": "flat_reference",
                "start_utc": "2026-09-01T00:00:00Z",
                "duration_hours": 2,
                "step_minutes": 60,
                "include_terrain": False,
            })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["site"]["site_id"], "flat_reference")
        self.assertIsNone(body["time_series"][2]["sun_alt_deg"])
        self.assertEqual(body["simultaneous_visible_pct"], 66.66666666666666)
        self.assertEqual(len(body["golden_windows"]), 1)
        self.assertEqual(body["golden_windows"][0]["duration_hours"], 1.0)

    def test_synthetic_profile_is_returned_as_display_only(self) -> None:
        with patch("backend.main.analysis.analyze", return_value=self._fixture()) as analyze:
            response = self.request("POST", "/api/analyze", json={
                "site_id": "flat_reference",
                "start_utc": "2026-09-01T00:00:00Z",
                "duration_hours": 2,
                "step_minutes": 60,
                "include_terrain": True,
            })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["provenance"]["horizon_source"], "geometric")
        self.assertEqual(body["provenance"]["display_horizon_source"], "synthetic")
        self.assertIn("not applied", body["provenance"]["terrain_note"])
        self.assertIsNone(analyze.call_args.kwargs["profile"])
        self.assertFalse(analyze.call_args.kwargs["include_dem_mask"])

    def test_lola_profile_is_applied_and_provenance_is_returned(self) -> None:
        with patch("backend.main.analysis.analyze", return_value=self._fixture()) as analyze:
            response = self.request("POST", "/api/analyze", json={
                "site_id": "shackleton_rim_w",
                "start_utc": "2026-09-01T00:00:00Z",
                "duration_hours": 2,
                "step_minutes": 60,
                "include_terrain": True,
            })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["provenance"]["horizon_source"], "dem")
        self.assertEqual(body["horizon_profile"]["coverage_range_km"], 5.0)
        self.assertEqual(body["horizon_profile"]["resolution_m"], 5.0)
        self.assertIn("interpolated", body["provenance"]["terrain_note"])
        self.assertEqual(analyze.call_args.kwargs["profile"].source, "dem")

    def test_comparison_returns_scenario_delta(self) -> None:
        first = self._fixture("flat_reference", 50.0)
        second = self._fixture("shackleton_henson", 70.0)
        with patch("backend.main.analysis.analyze", side_effect=[first, second]):
            response = self.request("POST", "/api/compare", json={
                "scenario_a": {"site_id": "flat_reference", "start_utc": "2026-09-01T00:00:00Z", "duration_hours": 2, "step_minutes": 60, "include_terrain": False},
                "scenario_b": {"site_id": "shackleton_henson", "start_utc": "2026-09-02T00:00:00Z", "duration_hours": 2, "step_minutes": 60, "include_terrain": False},
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["scenario_b_minus_a"]["sun_above_real_horizon_pct"], 20.0)

    def test_request_sampling_limit_is_validated(self) -> None:
        response = self.request("POST", "/api/analyze", json={
            "site_id": "flat_reference",
            "start_utc": "2026-09-01T00:00:00Z",
            "duration_hours": 120,
            "step_minutes": 1,
        })
        self.assertEqual(response.status_code, 422)

    def test_ml_predict_uses_the_saved_model_when_available(self) -> None:
        try:
            recommender.load_model()
        except Exception as exc:
            self.skipTest(f"Saved model cannot load in this environment: {exc}")
        response = self.request("POST", "/api/ml/predict", json={
            "site_ids": ["shackleton_henson"],
            "start_utc": "2026-11-15T00:00:00Z",
            "duration_hours": 24,
            "sample_hours": 6,
        })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["candidates"]), 3)
        self.assertTrue(all("score" in row and "explanation" in row for row in payload["candidates"]))

    def test_simulation_plan_reuses_existing_canvas_component(self) -> None:
        landing = pd.date_range("2026-06-04T02:10:00Z", periods=25, freq="1h")
        sky = ephemeris.SkyResult(
            times_utc=landing,
            sun_alt=np.full(25, 1.0),
            sun_az=np.linspace(0, 360, 25),
            earth_alt=np.full(25, 2.0),
            earth_az=np.linspace(180, 540, 25),
            backend="JPL Horizons test fixture",
        )
        with patch("backend.main.ephemeris.compute_sky", return_value=sky):
            response = self.request("POST", "/api/simulation/plan", json={
                "site_id": "flat_reference",
                "launch_utc": "2026-06-01T00:00:00Z",
                "transit_days": 3,
                "surface_days": 1,
                "step_minutes": 60,
            })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["horizon_profile"]["source"], "geometric")
        self.assertEqual(len(payload["surface_telemetry"]), 25)
        self.assertEqual(payload["landing_utc"], payload["surface_telemetry"][0]["time_utc"])
        self.assertEqual(payload["surface_telemetry"][0]["mission_seconds"], payload["phases"][-1]["start_seconds"])
        self.assertIn('id="simCanvas"', payload["simulator_html"])
        self.assertIn('id="timeSlider"', payload["simulator_html"])


if __name__ == "__main__":
    unittest.main()
