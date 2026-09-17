"""Register the selected Lab 2 model in the provider model registry."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow
import yaml

from cloudlayer.factory import get_adapter
from src import config


def require_match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Could not find {label}")
    return match.group(1).strip()


def read_data_version(tags: dict[str, str]) -> str:
    tracked = tags.get("dvc_data_hash")
    if tracked and tracked != "unknown":
        return tracked
    dvc_file = config.REPO_ROOT / "data" / "raw.dvc"
    metadata = yaml.safe_load(dvc_file.read_text())
    output = metadata["outs"][0]
    data_version = output.get("md5") or output.get("etag") or output.get("checksum")
    if not data_version:
        raise RuntimeError("Could not find a data hash in data/raw.dvc")
    return str(data_version)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cfg = config.load()
    reports = cfg.reports_dir
    run_id = (reports / "lab2-final-run-id.txt").read_text().strip()
    model_log = (reports / "lab2-final-model.log").read_text()
    image_log = (reports / "lab2-final-image-push.log").read_text()

    model_uri = require_match(r"^model_uri:\s+(gs://\S+)$", model_log, "model URI")
    training_job_id = require_match(r"^job_id:\s+(projects/\S+)$", model_log, "training job ID")
    image_uri = require_match(r"^(\S+@sha256:[0-9a-f]{64})$", image_log, "image URI")

    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    run = mlflow.tracking.MlflowClient().get_run(run_id)
    tags = run.data.tags
    params = run.data.params
    metrics = run.data.metrics

    metadata = {
        "git_commit": tags["git_commit"],
        "data_version": read_data_version(tags),
        "mlflow_run_id": run_id,
        "training_job_id": training_job_id,
        "image_digest": image_uri.split("@", 1)[1],
        "seed": int(params["seed"]),
        "metric_val": metrics["val_roc_auc"],
        "metric_test": metrics["test_roc_auc"],
        "image_uri": image_uri,
    }

    print("registering model with lineage:")
    print(json.dumps({key: value for key, value in metadata.items() if key != "image_uri"}, indent=2))
    if args.dry_run:
        print("PASS lineage is complete; no registry version was created")
        return 0
    version = get_adapter(cfg).register_model(model_uri, cfg.model_registry_name, metadata)
    (reports / "lab2-registry-version.txt").write_text(f"{version}\n")
    print(f"saved registry version: {reports / 'lab2-registry-version.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
