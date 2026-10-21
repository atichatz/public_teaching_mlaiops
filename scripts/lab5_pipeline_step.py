"""Cloud-side steps used by the Lab 5 Vertex AI managed pipeline.

The neutral DAG remains in ``pipeline/pipeline.yaml``.  This module contains the
provider-facing step implementation: artifacts are exchanged through one run-scoped
GCS prefix, while the evaluation decision is also emitted as a KFP string output so
the registration branch is a real managed-pipeline condition.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.cloud import aiplatform, storage


def _split_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected a gs:// URI, got {uri!r}")
    bucket, _, key = uri[5:].partition("/")
    if not bucket or not key:
        raise ValueError(f"GCS URI must include a bucket and object path: {uri!r}")
    return bucket, key


def _run_uri(base_uri: str, run_id: str) -> str:
    return f"{base_uri.rstrip('/')}/lab5/runs/{run_id}"


def _upload(local_path: Path, uri: str) -> None:
    bucket, key = _split_gcs(uri)
    storage.Client().bucket(bucket).blob(key).upload_from_filename(local_path)
    print(f"uploaded {local_path} -> {uri}")


def _download(uri: str, local_path: Path) -> None:
    bucket, key = _split_gcs(uri)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    storage.Client().bucket(bucket).blob(key).download_to_filename(local_path)
    print(f"downloaded {uri} -> {local_path}")


def ingest(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="lab5-ingest-") as tmp:
        dataset = Path(tmp) / "sensors.csv"
        subprocess.run(
            [sys.executable, "scripts/make_dataset.py", "--out", str(dataset)],
            check=True,
        )
        _upload(dataset, f"{_run_uri(args.base_uri, args.run_id)}/data/sensors.csv")
    return 0


def validate(args: argparse.Namespace) -> int:
    dataset = Path("data/raw/sensors.csv")
    _download(
        f"{_run_uri(args.base_uri, args.run_id)}/data/sensors.csv",
        dataset,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_data.py",
            "-k",
            "schema or no_nulls or plausible_ranges or target_is_binary or identifier_is_unique or no_machine_leaks",
        ],
        check=True,
    )
    return 0


def train(args: argparse.Namespace) -> int:
    run_uri = _run_uri(args.base_uri, args.run_id)
    with tempfile.TemporaryDirectory(prefix="lab5-train-") as tmp:
        root = Path(tmp)
        dataset = root / "sensors.csv"
        metrics = root / "metrics.json"
        model = root / "model.joblib"
        _download(f"{run_uri}/data/sensors.csv", dataset)
        env = {
            **os.environ,
            "MLFLOW_TRACKING_URI": f"sqlite:///{root / 'mlflow.db'}",
            "GIT_COMMIT": args.image_tag,
        }
        subprocess.run(
            [
                sys.executable,
                "-m",
                "src.train",
                "--data-path",
                str(dataset),
                "--metrics-out",
                str(metrics),
                "--model-out",
                str(model),
                "--n-estimators",
                "100",
                "--max-depth",
                "8",
                "--min-samples-leaf",
                "5",
                "--run-name",
                f"lab5-{args.run_id}",
            ],
            check=True,
            env=env,
        )
        _upload(metrics, f"{run_uri}/metrics/metrics.json")
        _upload(model, f"{run_uri}/model/model.joblib")
    return 0


def evaluate(args: argparse.Namespace) -> int:
    run_uri = _run_uri(args.base_uri, args.run_id)
    decision_out = Path(args.decision_out)
    decision_out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lab5-evaluate-") as tmp:
        metrics = Path(tmp) / "metrics.json"
        _download(f"{run_uri}/metrics/metrics.json", metrics)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/evaluation_gate.py",
                "--metrics",
                str(metrics),
                "--incumbent",
                str(args.incumbent),
                "--decision-out",
                str(decision_out),
            ],
            check=False,
        )
        if completed.returncode not in (0, 1):
            return completed.returncode
        decision = decision_out.read_text().strip()
        _upload(decision_out, f"{run_uri}/gate/decision.txt")
        print(f"managed gate decision: {decision}")
    # A failed model gate is a successful evaluation task.  The KFP condition uses
    # the emitted value to skip registration and deployment.
    return 0


def register(args: argparse.Namespace) -> int:
    run_uri = _run_uri(args.base_uri, args.run_id)
    artifact_uri = f"{run_uri}/model"
    aiplatform.init(
        project=args.project_id,
        location=args.region,
        staging_bucket=args.base_uri,
    )
    existing = aiplatform.Model.list(
        filter=f'display_name="{args.model_name}"',
        project=args.project_id,
        location=args.region,
    )
    environment = {
        "CLOUD_PROVIDER": "gcp",
        "PROJECT_ID": args.project_id,
        "REGION": args.region,
        "BLOB_URI": args.base_uri,
        "CONTAINER_REGISTRY": args.container_registry,
        "MLFLOW_TRACKING_URI": "sqlite:////tmp/mlflow.db",
        "MODEL_REGISTRY_NAME": args.model_name,
        "MODEL_ARTIFACT_URI": f"{artifact_uri}/model.joblib",
        "MODEL_VERSION": args.run_id,
        "IDENTITY_REF": args.serving_service_account,
    }
    upload_args = {
        "display_name": args.model_name,
        "artifact_uri": artifact_uri,
        "serving_container_image_uri": args.serving_image_uri,
        "serving_container_ports": [8080],
        "serving_container_health_route": "/ready",
        "serving_container_predict_route": "/predict",
        "serving_container_environment_variables": environment,
        "version_aliases": ["candidate"],
        "version_description": json.dumps(
            {
                "lab": 5,
                "run_id": args.run_id,
                "training_image": args.training_image_uri,
                "serving_image": args.serving_image_uri,
                "artifact_uri": artifact_uri,
            },
            sort_keys=True,
        ),
        "labels": {
            "course": "itcs355",
            "student": args.project_id,
            "lab": "5",
            "run": args.run_id.lower().replace("_", "-")[:63],
        },
        "project": args.project_id,
        "location": args.region,
        "staging_bucket": args.base_uri,
        "sync": True,
    }
    if existing:
        upload_args["parent_model"] = existing[0].resource_name
    else:
        upload_args["model_id"] = args.model_name
    model = aiplatform.Model.upload(**upload_args)
    output = Path(args.model_resource_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(model.versioned_resource_name + "\n")
    print(f"registered model: {model.versioned_resource_name}")
    return 0


def deploy(args: argparse.Namespace) -> int:
    model_resource = args.model_resource.strip()
    aiplatform.init(project=args.project_id, location=args.region)
    model = aiplatform.Model(model_name=model_resource)
    matches = aiplatform.Endpoint.list(
        filter=f'display_name="{args.endpoint_name}"',
        project=args.project_id,
        location=args.region,
    )
    endpoint = matches[0] if matches else aiplatform.Endpoint.create(
        display_name=args.endpoint_name,
        labels={"course": "itcs355", "student": args.project_id, "lab": "5"},
        project=args.project_id,
        location=args.region,
        sync=True,
    )
    if endpoint.list_models():
        raise RuntimeError(
            f"Endpoint {endpoint.resource_name} already has a deployed model; "
            "refusing to create an additional billable replica."
        )
    endpoint.deploy(
        model=model,
        deployed_model_display_name=f"lab5-{args.run_id}",
        machine_type=args.machine_type,
        min_replica_count=1,
        max_replica_count=1,
        traffic_percentage=100,
        service_account=args.serving_service_account,
        sync=True,
    )
    output = Path(args.endpoint_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(endpoint.resource_name + "\n")
    print(f"deployed endpoint: {endpoint.resource_name}")
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="step", required=True)

    def common(name: str) -> argparse.ArgumentParser:
        item = sub.add_parser(name)
        item.add_argument("--base-uri", required=True)
        item.add_argument("--run-id", required=True)
        return item

    common("ingest").set_defaults(func=ingest)
    common("validate").set_defaults(func=validate)

    train_parser = common("train")
    train_parser.add_argument("--image-tag", required=True)
    train_parser.set_defaults(func=train)

    evaluate_parser = common("evaluate")
    evaluate_parser.add_argument("--incumbent", type=float, required=True)
    evaluate_parser.add_argument("--decision-out", required=True)
    evaluate_parser.set_defaults(func=evaluate)

    register_parser = common("register")
    register_parser.add_argument("--project-id", required=True)
    register_parser.add_argument("--region", required=True)
    register_parser.add_argument("--model-name", required=True)
    register_parser.add_argument("--training-image-uri", required=True)
    register_parser.add_argument("--serving-image-uri", required=True)
    register_parser.add_argument("--container-registry", required=True)
    register_parser.add_argument("--serving-service-account", required=True)
    register_parser.add_argument("--model-resource-out", required=True)
    register_parser.set_defaults(func=register)

    deploy_parser = sub.add_parser("deploy")
    deploy_parser.add_argument("--project-id", required=True)
    deploy_parser.add_argument("--region", required=True)
    deploy_parser.add_argument("--run-id", required=True)
    deploy_parser.add_argument("--model-resource", required=True)
    deploy_parser.add_argument("--endpoint-name", required=True)
    deploy_parser.add_argument("--machine-type", default="n1-standard-2")
    deploy_parser.add_argument("--serving-service-account", required=True)
    deploy_parser.add_argument("--endpoint-out", required=True)
    deploy_parser.set_defaults(func=deploy)
    return ap


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
