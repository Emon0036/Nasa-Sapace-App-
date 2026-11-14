"""Fast, offline regression tests for the scientific and data-prep core."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd

from src import analysis, ephemeris, horizon, recommender, sim
from src.horizons import _parse_rows
from src.sites import Site, get_site


class TopocentricGeometryTests(unittest.TestCase):
    def test_enu_basis_is_orthonormal_at_poles_and_equator(self) -> None:
        for latitude, longitude in ((-90.0, 0.0), (-89.5, 160.0), (0.0, 0.0), (90.0, 90.0)):
            basis = ephemeris._enu_basis(latitude, longitude)
            np.testing.assert_allclose(basis @ basis.T, np.eye(3), atol=1e-12)
            self.assertAlmostEqual(float(np.linalg.det(basis)), 1.0, places=12)

    def test_south_pole_up_axis_points_to_south(self) -> None:
        up = ephemeris._enu_basis(-90.0, 15.0)[2]
        np.testing.assert_allclose(up, [0.0, 0.0, -1.0], atol=1e-12)

    def test_topocentric_cardinal_directions(self) -> None:
        latitude, longitude, elevation = -89.5, 160.0, 120.0
        observer = ephemeris._site_position_me(latitude, longitude, elevation)
        east, north, up = ephemeris._enu_basis(latitude, longitude)
        altitude, azimuth = ephemeris.topocentric_altaz(observer + 100.0 * east, latitude, longitude, elevation)
        self.assertAlmostEqual(altitude, 0.0, places=8)
        self.assertAlmostEqual(azimuth, 90.0, places=8)
        altitude, azimuth = ephemeris.topocentric_altaz(observer + 100.0 * north, latitude, longitude, elevation)
        self.assertAlmostEqual(altitude, 0.0, places=8)
        self.assertAlmostEqual(azimuth, 0.0, places=8)
        altitude, _ = ephemeris.topocentric_altaz(observer + 100.0 * up, latitude, longitude, elevation)
        self.assertAlmostEqual(altitude, 90.0, places=8)

    def test_no_unvalidated_analytic_fallback_is_advertised(self) -> None:
        with patch.object(ephemeris, "using_spice", return_value=False):
            with self.assertRaises(RuntimeError):
                ephemeris.sun_earth_in_lunar_frame([datetime(2026, 6, 1, tzinfo=timezone.utc)])


class HorizonTests(unittest.TestCase):
    def test_horizon_interpolation_wraps_across_zero_degrees(self) -> None:
        profile = horizon.HorizonProfile(
            azimuth_deg=np.array([0.0, 90.0, 180.0, 270.0]),
            elevation_deg=np.array([0.0, 10.0, 20.0, 30.0]),
            site_lat_deg=-89.5,
            site_lon_deg=0.0,
            site_elev_m=0.0,
            source="synthetic",
        )
        self.assertAlmostEqual(profile.horizon_altitude_at(315.0), 15.0)
        self.assertAlmostEqual(profile.horizon_altitude_at(360.0), 0.0)

    def test_synthetic_horizon_is_marked_as_synthetic(self) -> None:
        profile = horizon.synthetic_polar_horizon(-89.5, 0.0)
        self.assertEqual(profile.source, "synthetic")
        self.assertTrue(np.isfinite(profile.elevation_deg).all())

    def test_bundled_lola_profile_has_source_and_coverage_metadata(self) -> None:
        profile = horizon.horizon_for_site("shackleton_rim_w", -89.55, 225.0, 1850.0)
        self.assertEqual(profile.source, "dem")
        self.assertEqual(profile.coverage_range_km, 5.0)
        self.assertEqual(profile.resolution_m, 5.0)
        self.assertIn("Site01", profile.source_detail or "")
        self.assertTrue(np.isfinite(profile.elevation_deg).all())

    def test_lola_profile_is_not_reused_for_different_coordinates(self) -> None:
        profile = horizon.horizon_for_site("shackleton_rim_w", -89.45, 160.0, 1450.0)
        self.assertEqual(profile.source, "synthetic")

    def test_custom_coordinate_can_build_a_covered_lola_profile(self) -> None:
        profile = horizon.horizon_for_site(
            "custom-lola-test",
            -89.55,
            225.0,
            1850.0,
            generate_from_tiles=True,
        )
        self.assertEqual(profile.source, "dem")
        self.assertEqual(profile.coverage_range_km, 5.0)
        self.assertIn("Site01", profile.source_detail or "")

    def test_lola_obstruction_changes_scientific_visibility_mask(self) -> None:
        site = get_site("shackleton_rim_w")
        profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
        peak_index = int(np.argmax(profile.elevation_deg))
        azimuth = float(profile.azimuth_deg[peak_index])
        altitude = float(profile.elevation_deg[peak_index] - 0.1)
        times = pd.date_range("2026-06-01T00:00:00Z", periods=3, freq="1h")
        sky = ephemeris.SkyResult(
            times_utc=times,
            sun_alt=np.full(3, altitude),
            sun_az=np.full(3, azimuth),
            earth_alt=np.full(3, altitude),
            earth_az=np.full(3, azimuth),
            backend="fixture",
        )
        with patch.object(ephemeris, "compute_sky", return_value=sky):
            frame, summary = analysis.analyze(
                site,
                times[0].to_pydatetime(),
                duration_hours=2,
                step_minutes=60,
                profile=profile,
                include_dem_mask=True,
            )
        self.assertEqual(summary.sun_above_horizon_pct, 100.0)
        self.assertEqual(summary.sun_above_real_horizon_pct, 0.0)
        self.assertFalse(frame["sun_visible"].any())
        self.assertTrue(np.all(frame["sun_horizon_deg"].to_numpy() > altitude))

    def test_synthetic_profile_is_not_applied_as_measured_terrain(self) -> None:
        site = get_site("flat_reference")
        times = pd.date_range("2026-06-01T00:00:00Z", periods=3, freq="1h")
        sky = ephemeris.SkyResult(
            times_utc=times,
            sun_alt=np.full(3, 0.5),
            sun_az=np.full(3, 0.0),
            earth_alt=np.full(3, 0.5),
            earth_az=np.full(3, 180.0),
            backend="fixture",
        )
        profile = horizon.synthetic_polar_horizon(site.lat_deg, site.lon_deg, site.elev_m)
        self.assertGreater(profile.horizon_altitude_at(0.0), 0.5)
        with patch.object(ephemeris, "compute_sky", return_value=sky):
            frame, _ = analysis.analyze(
                site, times[0].to_pydatetime(), duration_hours=2.0,
                step_minutes=60.0, profile=profile, include_dem_mask=True,
            )
        self.assertTrue(frame["sun_visible"].all())
        self.assertTrue(frame["earth_visible"].all())
        self.assertNotIn("sun_horizon_deg", frame.columns)

    def test_seasonal_cached_sweep_uses_geometric_horizon_without_dem(self) -> None:
        site = get_site("flat_reference")
        cached = pd.DataFrame({
            "time_utc": pd.date_range("2026-06-01T00:00:00Z", periods=5, freq="6h"),
            "site_id": site.site_id,
            "sun_alt_deg": np.full(5, 0.5),
            "sun_az_deg": np.full(5, 0.0),
            "earth_alt_deg": np.full(5, 0.5),
            "earth_az_deg": np.full(5, 180.0),
            "ephemeris_source": "fixture",
        })
        with patch.object(analysis, "_cached_ephemeris_for_site", return_value=cached):
            swept = analysis.date_sweep(
                site, datetime(2026, 6, 1, tzinfo=timezone.utc), n_dates=1,
                duration_hours=24.0, include_dem_mask=True,
            )
        self.assertEqual(float(swept.iloc[0]["sun_above_real_horizon_pct"]), 100.0)
        self.assertEqual(float(swept.iloc[0]["earth_above_real_horizon_pct"]), 100.0)

    def test_seasonal_cached_sweep_respects_requested_duration(self) -> None:
        site = get_site("flat_reference")
        cached = pd.DataFrame({
            "time_utc": pd.date_range("2026-06-01T00:00:00Z", periods=21, freq="6h"),
            "site_id": site.site_id,
            "sun_alt_deg": np.full(21, 0.5),
            "sun_az_deg": np.full(21, 0.0),
            "earth_alt_deg": np.full(21, 0.5),
            "earth_az_deg": np.full(21, 180.0),
            "ephemeris_source": "fixture",
        })
        with patch.object(analysis, "_cached_ephemeris_for_site", return_value=cached):
            swept = analysis.date_sweep(
                site, datetime(2026, 6, 1, tzinfo=timezone.utc), n_dates=1,
                duration_hours=120.0, include_dem_mask=False,
            )
        self.assertEqual(float(swept.iloc[0]["sunlit_continuous_hours_max"]), 120.0)

    def test_simulator_uses_geometric_visibility_without_dem(self) -> None:
        site = get_site("flat_reference")
        times = pd.date_range("2026-06-04T02:10:00Z", periods=3, freq="12h")
        sky = ephemeris.SkyResult(
            times_utc=times,
            sun_alt=np.array([1.0, 2.0, 3.0]),
            sun_az=np.array([0.0, 120.0, 240.0]),
            earth_alt=np.array([1.0, 2.0, 3.0]),
            earth_az=np.array([180.0, 240.0, 300.0]),
            backend="fixture",
        )
        with patch.object(ephemeris, "compute_sky", return_value=sky) as compute_sky:
            plan = sim.plan_mission(
                site, datetime(2026, 6, 1, tzinfo=timezone.utc),
                transit_days=3.0, surface_days=1.0, step_minutes=720.0,
            )
        self.assertEqual(plan.profile.source, "geometric")
        np.testing.assert_allclose(plan.horizon_at, np.zeros(3))
        expected_surface_start = datetime(2026, 6, 4, 2, 10, tzinfo=timezone.utc)
        self.assertEqual(compute_sky.call_args.args[0][0], expected_surface_start)
        self.assertEqual(plan.surface_times[0], expected_surface_start)


class HorizonsDataTests(unittest.TestCase):
    def test_observer_parser_reads_airless_azimuth_and_elevation(self) -> None:
        payload = {
            "result": "header\n$$SOE\n"
            " 2026-Jun-01 00:00:00.000  352.930351  -1.088483\n"
            " 2026-Jun-01 00:15:00.000  352.802399  -1.088480\n$$EOE\nfooter"
        }
        parsed = _parse_rows(payload, "Sun")
        self.assertEqual(len(parsed), 2)
        self.assertAlmostEqual(float(parsed.iloc[0]["az_deg"]), 352.930351)
        self.assertAlmostEqual(float(parsed.iloc[0]["alt_deg"]), -1.088483)
        self.assertEqual(str(parsed.index.tz), "UTC")

    def test_summary_uses_elapsed_intervals_not_sample_count(self) -> None:
        site = get_site("flat_reference")
        times = pd.date_range("2026-06-01T00:00:00Z", periods=3, freq="1h")
        sky = ephemeris.SkyResult(
            times_utc=times,
            sun_alt=np.array([2.0, 2.0, -1.0]),
            sun_az=np.array([0.0, 0.0, 0.0]),
            earth_alt=np.array([5.0, 5.0, 5.0]),
            earth_az=np.array([90.0, 90.0, 90.0]),
            backend="JPL Horizons test fixture",
        )
        with patch.object(ephemeris, "compute_sky", return_value=sky):
            frame, summary = analysis.analyze(
                site, times[0].to_pydatetime(), duration_hours=2.0,
                step_minutes=60.0, include_dem_mask=False,
            )
        self.assertEqual(len(frame), 3)
        self.assertAlmostEqual(summary.duration_hours, 2.0)
        self.assertAlmostEqual(summary.sunlit_continuous_hours_max, 1.0)
        self.assertAlmostEqual(summary.earth_blackout_minutes, 0.0)


class RecommendationCoverageTests(unittest.TestCase):
    def test_longitude_wrap_uses_short_angular_distance(self) -> None:
        near_wrap = Site("custom", "Custom", -89.5, 359.8, 0.0, "test", "custom")
        model = {"training_locations": [{
            "latitude_deg": -89.5,
            "longitude_deg_east": 0.0,
            "elevation_m": 0.0,
        }]}
        self.assertLess(recommender._nearest_training_location_deg(near_wrap, model), 0.01)


if __name__ == "__main__":
    unittest.main()
