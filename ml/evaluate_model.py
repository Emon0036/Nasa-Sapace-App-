"""Print the metrics recorded for the latest chronological-grouped evaluation."""

from __future__ import annotations

import json
from pathlib import Path

METRICS_PATH = Path(__file__).resolve().parent / "metrics.json"


def main() -> None:
    if not METRICS_PATH.exists():
        raise FileNotFoundError("Run ml/train_model.py first")
    print(json.dumps(json.loads(METRICS_PATH.read_text(encoding="utf-8")), indent=2))


if __name__ == "__main__":
    main()
