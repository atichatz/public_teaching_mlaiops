"""Register a Vertex AI model version that uses the Lab 3 serving image."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.cloud import aiplatform

from cloudlayer.factory import get_adapter
from src import config


def main() -> int:
    cfg = config.load()
    reports = cfg.reports_dir

    source_version = (
        reports / "lab2-registry-version.txt"
    ).read_text().strip()

    image_lines = [
        line.strip()
        for line in (
            reports / "lab3-serving-image-uri.txt"
        ).read_text().splitlines()
        if "@sha256:" in line
    ]

    if not image_lines:
        raise RuntimeError(
            "No digest-pinned serving image found in "
            "reports/lab3-serving-image-uri.txt"
        )

    serving_image = image_lines[-1]

    adapter = get_adapter(cfg)
    registered = adapter.resolve_registered_model(
        cfg.model_registry_name,
        source_version,
    )

    artifact_uri = registered["artifact_uri"]
    parent_model = registered["name"].split("@", 1)[0]

    environment = {
        "CLOUD_PROVIDER": cfg.provider,
        "PROJECT_ID": cfg.project_id,
        "REGION": cfg.region,
        "BLOB_URI": cfg.blob_uri,
        "CONTAINER_REGISTRY": cfg.container_registry,
        "MLFLOW_TRACKING_URI": cfg.mlflow_tracking_uri,
        "MODEL_REGISTRY_NAME": cfg.model_registry_name,
        "MODEL_VERSION": source_version,
        "IDENTITY_REF": cfg.identity_ref,
    }

    description = {
        "purpose": "lab3-batch-serving",
        "source_model_version": source_version,
        "serving_image": serving_image,
        "health_route": "/ready",
        "predict_route": "/predict/batch",
    }

    aiplatform.init(
        project=cfg.project_id,
        location=cfg.region,
    )

    model = aiplatform.Model.upload(
        display_name=cfg.model_registry_name,
        parent_model=parent_model,
        artifact_uri=artifact_uri,
        serving_container_image_uri=serving_image,
        serving_container_ports=[8080],
        serving_container_health_route="/ready",
        serving_container_predict_route="/predict/batch",
        serving_container_environment_variables=environment,
        version_aliases=["lab3-batch"],
        version_description=json.dumps(
            description,
            sort_keys=True,
        ),
        labels=cfg.tags(3),
        project=cfg.project_id,
        location=cfg.region,
        sync=True,
    )

    (reports / "lab3-batch-model.txt").write_text(
        model.versioned_resource_name + "\n"
    )
    (reports / "lab3-batch-version.txt").write_text(
        str(model.version_id) + "\n"
    )

    print(f"serving model: {model.versioned_resource_name}")
    print(f"version: {model.version_id}")
    print(f"artifact: {artifact_uri}")
    print(f"image: {serving_image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())