"""Submit the compiled Lab 5 pipeline to Vertex AI without waiting."""
from __future__ import annotations

import argparse
from pathlib import Path

from google.cloud import aiplatform


def digest_uri(value: str) -> str:
    """Reject mutable container tags at the cloud submission boundary."""
    if "@sha256:" not in value:
        raise argparse.ArgumentTypeError("image URI must contain @sha256:")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--pipeline-root", required=True)
    parser.add_argument("--base-uri", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--serving-image-uri", type=digest_uri, required=True)
    parser.add_argument("--container-registry", required=True)
    parser.add_argument("--pipeline-service-account", required=True)
    parser.add_argument("--serving-service-account", required=True)
    parser.add_argument("--incumbent", type=float, default=0.847)
    parser.add_argument("--model-name", default="itcs355-lab5")
    parser.add_argument("--endpoint-name", default="itcs355-lab5-staging")
    parser.add_argument("--machine-type", default="n1-standard-2")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.template.is_file():
        raise FileNotFoundError(args.template)

    aiplatform.init(
        project=args.project,
        location=args.region,
        staging_bucket=args.pipeline_root,
    )
    job = aiplatform.PipelineJob(
        display_name=f"itcs355-lab5-{args.run_id}",
        job_id=f"itcs355-lab5-{args.run_id}",
        template_path=str(args.template),
        pipeline_root=args.pipeline_root,
        parameter_values={
            "project_id": args.project,
            "region": args.region,
            "base_uri": args.base_uri,
            "run_id": args.run_id,
            "image_tag": args.image_tag,
            "serving_image_uri": args.serving_image_uri,
            "container_registry": args.container_registry,
            "serving_service_account": args.serving_service_account,
            "incumbent": args.incumbent,
            "model_name": args.model_name,
            "endpoint_name": args.endpoint_name,
            "machine_type": args.machine_type,
        },
        enable_caching=False,
        labels={"lab": "5", "course": "itcs355"},
    )
    job.submit(service_account=args.pipeline_service_account)
    print(f"PIPELINE_RESOURCE={job.resource_name}")
    print(f"RUN_ID={args.run_id}")
    print("SUBMITTED_ASYNC=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
