import math
import unittest
from datetime import datetime, timezone

import numpy as np

from src import analysis, ephemeris


class CoordinateTransformTests(unittest.TestCase):
    def test_analytic_up_vector_is_vertical_at_south_pole(self):
        lat_deg = -89.45
        lon_deg = 160.0
        lat = math.radians(lat_deg)
        lon = math.radians(lon_deg)
        up = np.array([
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
        ])

        alt, _ = ephemeris._low_precision_topocentric(
            up.reshape(1, 3), lat_deg, lon_deg,
        )

        self.assertAlmostEqual(float(alt[0]), 90.0, places=10)

    @unittest.skipUnless(ephemeris.using_spice(), "SPICE kernels unavailable")
    def test_spice_up_vector_is_vertical_at_south_pole(self):
        lat_deg = -89.45
        lon_deg = 160.0
        lat = math.radians(lat_deg)
        lon = math.radians(lon_deg)
        up = np.array([
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
        ])
        et = ephemeris.to_et(datetime(2026, 11, 1, tzinfo=timezone.utc))

        alt, _ = ephemeris.topocentric_altaz(
            up, lat_deg, lon_deg, et=et,
        )

        self.assertAlmostEqual(float(alt), 90.0, places=8)


class AnalysisTests(unittest.TestCase):
    def test_terminal_run_does_not_extend_past_window(self):
        samples = np.ones(97, dtype=bool)  # 00:00 through 24:00, 15 min step
        self.assertEqual(analysis._continuous_runs(samples, 0.25), [24.0])


if __name__ == "__main__":
    unittest.main()
