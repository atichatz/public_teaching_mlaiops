"""Compare 100 single predictions with one 100-row batch request."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config


SAMPLE = {
    "temp_c": 78.4,
    "vibration_mm_s": 3.1,
    "pressure_kpa": 315.2,
    "hours_since_service": 4200,
    "load_pct": 68.0,
    "ambient_humidity": 55.0,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("single", "batch"),
        required=True,
    )
    args = parser.parse_args()

    cfg = config.load()
    endpoint = (
        cfg.reports_dir / "lab3-endpoint.txt"
    ).read_text().strip()

    adapter = get_adapter(cfg)

    if args.mode == "single":
        # Warm-up request. It is not included in the measured result.
        warmup = adapter.invoke(endpoint, SAMPLE)
        if "probability" not in warmup:
            raise RuntimeError(
                f"Single warm-up failed: {warmup}"
            )

        started = time.perf_counter()
        probabilities = []

        for _ in range(100):
            response = adapter.invoke(endpoint, SAMPLE)
            probability = response.get("probability")

            if probability is None:
                raise RuntimeError(
                    f"Single prediction failed: {response}"
                )

            probabilities.append(float(probability))

        elapsed = time.perf_counter() - started
        request_count = 100

    else:
        warmup = adapter.invoke(
            endpoint,
            {"rows": [SAMPLE]},
        )

        if len(warmup.get("probabilities", [])) != 1:
            raise RuntimeError(
                f"Batch warm-up failed: {warmup}"
            )

        payload = {
            "rows": [SAMPLE for _ in range(100)]
        }

        started = time.perf_counter()
        response = adapter.invoke(endpoint, payload)
        elapsed = time.perf_counter() - started

        probabilities = response.get("probabilities", [])
        if len(probabilities) != 100:
            raise RuntimeError(
                "Batch response did not contain "
                f"100 probabilities: {response}"
            )

        request_count = 1

    result = {
        "mode": args.mode,
        "requests": request_count,
        "predictions": len(probabilities),
        "elapsed_seconds": elapsed,
        "predictions_per_second": (
            len(probabilities) / elapsed
        ),
        "milliseconds_per_prediction": (
            elapsed * 1000 / len(probabilities)
        ),
    }

    output = (
        cfg.reports_dir
        / f"lab3-batch-{args.mode}.json"
    )
    output.write_text(
        json.dumps(result, indent=2) + "\n"
    )

    print(json.dumps(result, indent=2))
    print(f"saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())