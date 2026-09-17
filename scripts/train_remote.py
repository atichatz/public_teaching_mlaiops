"""Submit one smoke-test training job to managed compute."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from cloudlayer.factory import get_adapter
from src import config, seeds
from src.train import dvc_data_hash, git_commit


def gcs_mount_path(uri: str) -> str:
    """Convert gs://bucket/object to Vertex AI's /gcs mount path."""
    parsed = urlparse(uri)

    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"Expected a GCS URI, got {uri!r}")

    object_path = parsed.path.lstrip("/")
    return f"/gcs/{parsed.netloc}/{object_path}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit one Vertex AI smoke-test training job"
    )
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--instance", default="e2-standard-4")
    parser.add_argument("--seed", type=int, default=seeds.DEFAULT_SEED)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--min-samples-leaf", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = config.load()
    adapter = get_adapter(cfg)

    if "@sha256:" not in args.image_uri:
        raise ValueError(
            "--image-uri must be digest-pinned and contain @sha256:"
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_name = f"itcs355-lab2-smoke-{timestamp}"

    blob_root = cfg.blob_uri.rstrip("/")
    data_uri = f"{blob_root}/lab2/data/sensors.csv"
    output_uri = f"{blob_root}/lab2/jobs/{job_name}"
    metrics_uri = f"{output_uri}/metrics.json"
    model_uri = f"{output_uri}/model.joblib"

    container_args = [
        "--experiment",
        "itcs355-lab2-remote-smoke",
        "--run-name",
        job_name,
        "--data-path",
        gcs_mount_path(data_uri),
        "--metrics-out",
        gcs_mount_path(metrics_uri),
        "--model-out",
        gcs_mount_path(model_uri),
        "--seed",
        str(args.seed),
        "--n-estimators",
        str(args.n_estimators),
        "--max-depth",
        str(args.max_depth),
        "--min-samples-leaf",
        str(args.min_samples_leaf),
    ]

    submit_args = {
        "job_name": job_name,
        "instance": args.instance,
        "output_uri": output_uri,
        "container_args": container_args,
        "env": {
            "GIT_COMMIT": git_commit(),
            "DVC_DATA_HASH": dvc_data_hash(),
            # The remote SQLite database is temporary. The durable
            # metrics and model are written to GCS separately.
            "MLFLOW_TRACKING_URI": "sqlite:////tmp/mlflow.db",
        },
    }

    print(f"submitting job: {job_name}")
    print(f"data:           {data_uri}")
    print(f"output:         {output_uri}")

    job_id = adapter.submit_training(args.image_uri, submit_args)
    print(f"job_id:         {job_id}")

    result = adapter.wait_training(job_id)
    print(json.dumps(result, indent=2))

    local_metrics = Path("/tmp") / f"{job_name}-metrics.json"
    adapter.download(metrics_uri, str(local_metrics))

    print(f"downloaded:     {local_metrics}")
    print(local_metrics.read_text())
    print(f"model_uri:      {model_uri}")
    print("PASS remote training completed and artifacts were recovered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
