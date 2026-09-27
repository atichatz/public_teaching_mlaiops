"""Invoke the deployed endpoint with three known payloads."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config


PAYLOADS = [
    {
        "temp_c": 78.4,
        "vibration_mm_s": 3.1,
        "pressure_kpa": 315.2,
        "hours_since_service": 4200,
        "load_pct": 68,
        "ambient_humidity": 55,
    },
    {
        "temp_c": 90.0,
        "vibration_mm_s": 7.0,
        "pressure_kpa": 340.0,
        "hours_since_service": 8000,
        "load_pct": 90,
        "ambient_humidity": 70,
    },
    {
        "temp_c": 55.0,
        "vibration_mm_s": 1.0,
        "pressure_kpa": 285.0,
        "hours_since_service": 500,
        "load_pct": 30,
        "ambient_humidity": 40,
    },
]


def main() -> int:
    cfg = config.load()
    endpoint = (
        cfg.reports_dir / "lab3-endpoint.txt"
    ).read_text().strip()

    adapter = get_adapter(cfg)

    for number, payload in enumerate(PAYLOADS, start=1):
        result = adapter.invoke(endpoint, payload)

        probability = result.get("probability")
        version = result.get("model_version")

        if probability is None:
            raise RuntimeError(
                f"payload {number}: probability missing: "
                f"{result}"
            )

        if not 0.0 <= float(probability) <= 1.0:
            raise RuntimeError(
                f"payload {number}: invalid probability: "
                f"{probability}"
            )

        if not version:
            raise RuntimeError(
                f"payload {number}: model_version missing"
            )

        print(
            f"PASS payload={number} "
            f"probability={float(probability):.6f} "
            f"model_version={version}"
        )

    print("PASS all smoke-test requests succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())