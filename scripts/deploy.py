"""Deploy the registered Lab 3 serving model."""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint",
        default=None,
    )
    parser.add_argument(
        "--instance",
        default="n1-standard-2",
    )
    args = parser.parse_args()

    cfg = config.load()
    reports = cfg.reports_dir
    lab_number = int(os.environ.get("LAB_NUMBER", "3"))

    model_ref = (
        reports / f"lab{lab_number}-serving-model.txt"
    ).read_text().strip()

    endpoint_name = (
        args.endpoint
        or f"{cfg.model_registry_name}-lab{lab_number}-staging"
    )

    adapter = get_adapter(cfg)
    resource_name = adapter.deploy(
        model_ref=model_ref,
        endpoint=endpoint_name,
        instance=args.instance,
    )

    output = reports / f"lab{lab_number}-endpoint.txt"
    output.write_text(resource_name + "\n")

    print(f"saved endpoint: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())