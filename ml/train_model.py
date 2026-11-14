"""Train and evaluate the JPL Horizons-derived condition surrogate.

The model learns a fast interpolation of JPL Horizons ephemeris outputs. It is
not trained on spacecraft observations and is not used as the authoritative
physics calculation.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.features import FEATURE_NAMES, make_features, make_targets

DATASET_PATH = ROOT / "data" / "processed" / "horizons_ephemeris.csv"
MANIFEST_PATH = ROOT / "data" / "processed" / "horizons_ephemeris.provenance.json"
MODEL_PATH = ROOT / "ml" / "models" / "lunar_conditions_rf.joblib"
METRICS_PATH = ROOT / "ml" / "metrics.json"


def _circular_mae_deg(true_vectors: np.ndarray, predicted_vectors: np.ndarray) -> dict[str, float]:
    output: dict[str, float] = {}
    for label, sin_col, cos_col in (
        ("sun_azimuth", 0, 1), ("earth_azimuth", 2, 3),
    ):
        actual = np.rad2deg(np.arctan2(true_vectors[:, sin_col], true_vectors[:, cos_col])) % 360.0
        predicted = np.rad2deg(np.arctan2(predicted_vectors[:, sin_col], predicted_vectors[:, cos_col])) % 360.0
        difference = np.abs((actual - predicted + 180.0) % 360.0 - 180.0)
        output[f"{label}_circular_mae_deg"] = float(np.mean(difference))
    return output


def train() -> dict[str, object]:
    if not DATASET_PATH.exists() or not MANIFEST_PATH.exists():
        raise FileNotFoundError("Run data_pipeline/collect_nasa_data.py before training")
    data = pd.read_csv(DATASET_PATH, parse_dates=["time_utc"])
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    required = {"site_id", "time_utc", "latitude_deg", "longitude_deg_east", "elevation_m",
                "sun_alt_deg", "sun_az_deg", "earth_alt_deg", "earth_az_deg"}
    if not required.issubset(data.columns):
        raise ValueError(f"Dataset is missing columns: {sorted(required.difference(data.columns))}")
    if len(data) < 250 or data[list(required)].isna().any().any():
        raise ValueError("Training data is too small or contains missing required values")
    if data["ephemeris_source"].astype(str).str.contains("Horizons", case=False).mean() < 1.0:
        raise ValueError("Training labels must all come from NASA/JPL Horizons")

    features = make_features(data)
    y_alt, y_az = make_targets(data)
    groups = pd.to_datetime(data["time_utc"], utc=True).dt.strftime("%Y-%m-%d").to_numpy()
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(splitter.split(features, y_alt, groups=groups))

    altitude_model = RandomForestRegressor(
        n_estimators=120,
        max_depth=12,
        min_samples_leaf=4,
        max_features=0.9,
        n_jobs=-1,
        random_state=42,
    )
    azimuth_model = RandomForestRegressor(
        n_estimators=120,
        max_depth=12,
        min_samples_leaf=4,
        max_features=0.9,
        n_jobs=-1,
        random_state=43,
    )
    altitude_model.fit(features.iloc[train_idx], y_alt[train_idx])
    azimuth_model.fit(features.iloc[train_idx], y_az[train_idx])
    predicted_alt = altitude_model.predict(features.iloc[test_idx])
    predicted_az = azimuth_model.predict(features.iloc[test_idx])

    baseline = np.tile(np.mean(y_alt[train_idx], axis=0), (len(test_idx), 1))
    target_metrics: dict[str, dict[str, float]] = {}
    for column, label in enumerate(("sun_altitude_deg", "earth_altitude_deg")):
        target_metrics[label] = {
            "model_mae_deg": float(mean_absolute_error(y_alt[test_idx, column], predicted_alt[:, column])),
            "model_rmse_deg": float(np.sqrt(mean_squared_error(y_alt[test_idx, column], predicted_alt[:, column]))),
            "model_r2": float(r2_score(y_alt[test_idx, column], predicted_alt[:, column])),
            "mean_baseline_mae_deg": float(mean_absolute_error(y_alt[test_idx, column], baseline[:, column])),
            "mean_baseline_rmse_deg": float(np.sqrt(mean_squared_error(y_alt[test_idx, column], baseline[:, column]))),
            "mean_baseline_r2": float(r2_score(y_alt[test_idx, column], baseline[:, column])),
        }

    metrics: dict[str, object] = {
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "RandomForestRegressor (two outputs: Sun/Earth altitude) + RandomForestRegressor (cyclic azimuth components)",
        "dataset_source": "NASA/JPL Horizons API, JPL planetary solution stated in provenance manifest",
        "dataset_path": str(DATASET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "dataset_rows": int(len(data)),
        "site_count": int(data["site_id"].nunique()),
        "date_coverage_utc": [pd.to_datetime(data["time_utc"], utc=True).min().isoformat(),
                              pd.to_datetime(data["time_utc"], utc=True).max().isoformat()],
        "split": {
            "method": "GroupShuffleSplit by UTC calendar day; no timestamps from one date are split across train/test",
            "test_size": 0.20,
            "random_state": 42,
            "train_rows": int(len(train_idx)),
            "test_rows": int(len(test_idx)),
            "train_dates": int(pd.Series(groups[train_idx]).nunique()),
            "test_dates": int(pd.Series(groups[test_idx]).nunique()),
        },
        "features": FEATURE_NAMES,
        "altitude_targets": ["sun_altitude_deg", "earth_altitude_deg"],
        "altitude_metrics": target_metrics,
        "azimuth_metrics": _circular_mae_deg(y_az[test_idx], predicted_az),
        "label_provenance": "Computed apparent, airless topocentric azimuth/elevation from JPL Horizons; not instrument observations.",
        "interpretation": "Interpolation surrogate within the Horizons date/coordinate coverage; not a future forecast or a replacement for Horizons/SPICE.",
        "provenance_manifest": str(MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
    }
    artifact = {
        "format_version": 1,
        "feature_names": FEATURE_NAMES,
        "altitude_model": altitude_model,
        "azimuth_model": azimuth_model,
        "date_min_utc": pd.to_datetime(data["time_utc"], utc=True).min().isoformat(),
        "date_max_utc": pd.to_datetime(data["time_utc"], utc=True).max().isoformat(),
        "site_ids": sorted(data["site_id"].astype(str).unique()),
        "dataset_rows": int(len(data)),
        "coordinate_bounds": {
            "latitude_deg": [float(data["latitude_deg"].min()), float(data["latitude_deg"].max())],
            "longitude_deg_east": [float(data["longitude_deg_east"].min()), float(data["longitude_deg_east"].max())],
            "elevation_m": [float(data["elevation_m"].min()), float(data["elevation_m"].max())],
        },
        "training_locations": data.groupby("site_id", as_index=False).agg({
            "latitude_deg": "first",
            "longitude_deg_east": "first",
            "elevation_m": "first",
        }).to_dict(orient="records"),
        "data_source": manifest.get("source_url"),
        "target_solution": manifest.get("target_solution"),
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH, compress=3)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    train()
