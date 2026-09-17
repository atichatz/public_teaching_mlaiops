"""GCP adapter. Implement upload/download/push_image for Lab 1.

SDK:  pip install google-cloud-storage google-cloud-aiplatform
Docs: storage.Client for GCS; Artifact Registry push goes through `docker push` after
      `gcloud auth configure-docker <region>-docker.pkg.dev`.

Hints for Lab 1:
  * BLOB_URI looks like gs://bucket/prefix — parse it here, never in src/.
  * Artifact Registry paths are region-scoped:
        <region>-docker.pkg.dev/<project>/<repo>/<image>
    A common first failure is pushing to gcr.io out of habit; it is a different service.
  * push_image must return the digest reference, not the tag.
  * GCP calls them labels, not tags, and they must be lowercase with no spaces.
    cfg.tags(1) already satisfies that constraint — do not "improve" the values.
"""
import time
import re
import subprocess

from datetime import datetime, timezone
from typing import Any
from google.cloud import aiplatform

from pathlib import Path
from urllib.parse import urlparse
from google.cloud import storage
from cloudlayer.base import CloudAdapter

def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)

    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"Invalid GCS URI: {uri}")

    return parsed.netloc, parsed.path.lstrip("/")

class GcpAdapter(CloudAdapter):
    def upload(self, local_path: str, key: str) -> str:

        bucket_name, prefix = _parse_gcs_uri(self.cfg.blob_uri)
        object_name = "/".join(
            part.strip("/")
            for part in (prefix, key)
            if part.strip("/")
        )

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_filename(local_path)

        return f"gs://{bucket_name}/{object_name}"


    def download(self, uri: str, local_path: str) -> None:
        bucket_name, object_name = _parse_gcs_uri(uri)

        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.download_to_filename(str(destination))

    def push_image(self, local_tag: str) -> str:
        registry = self.cfg.container_registry.rstrip("/")
        registry_host = registry.split("/", 1)[0]
        image_name = local_tag.rsplit("/", 1)[-1]
        remote_tag = f"{registry}/{image_name}"

        subprocess.run(
            [
                "gcloud",
                "auth",
                "configure-docker",
                registry_host,
                "--quiet",
            ],
            check=True,
        )

        subprocess.run(
            ["docker", "tag", local_tag, remote_tag],
            check=True,
        )

        pushed = subprocess.run(
            ["docker", "push", remote_tag],
            capture_output=True,
            text=True,
            check=True,
        )

        output = pushed.stdout + pushed.stderr
        match = re.search(r"digest:\s*(sha256:[0-9a-f]{64})", output)

        if not match:
            raise RuntimeError(
                "Docker push succeeded but no image digest was found.\n"
                + output
            )

        repository = remote_tag.rsplit(":", 1)[0]
        return f"{repository}@{match.group(1)}"

    # submit_training / register_model  -> Lab 2 (Vertex custom training + Model Registry)
    # deploy / invoke                   -> Lab 3 (Vertex Endpoint)
    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
    # teardown                          -> Lab 5 (filter resources by label)
    def submit_training(
        self,
        image_uri: str,
        args: dict[str, Any],
    ) -> str:
        if "@sha256:" not in image_uri:
            raise ValueError(
                "Training image must be digest-pinned: repo@sha256:..."
            )

        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_name = args.get("job_name", f"itcs355-lab2-{timestamp}")
        output_uri = args["output_uri"]
        instance = args.get("instance", "e2-standard-4")

        environment = [
            {"name": key, "value": str(value)}
            for key, value in args.get("env", {}).items()
        ]

        worker_pool_specs = [{
            "machine_spec": {
                "machine_type": instance,
            },
            "replica_count": 1,
            "container_spec": {
                "image_uri": image_uri,
                "args": [
                    str(value)
                    for value in args["container_args"]
                ],
                "env": environment,
            },
        }]

        job = aiplatform.CustomJob(
            display_name=job_name,
            worker_pool_specs=worker_pool_specs,
            base_output_dir=output_uri,
            labels=self.cfg.tags(2),
        )

        job.submit(
            service_account=self.cfg.identity_ref,
            scheduling_strategy=(
                aiplatform.gapic.Scheduling.Strategy.SPOT
            ),
            restart_job_on_worker_restart=True,
            timeout=3600,
            max_wait_duration=3600,
        )

        return job.resource_name

    def wait_training(self, job_id: str) -> dict[str, Any]:
        client = aiplatform.gapic.JobServiceClient(
            client_options={
                "api_endpoint": (
                    f"{self.cfg.region}-aiplatform.googleapis.com"
                )
            }
        )

        succeeded = aiplatform.gapic.JobState.JOB_STATE_SUCCEEDED
        terminal_states = {
            succeeded,
            aiplatform.gapic.JobState.JOB_STATE_FAILED,
            aiplatform.gapic.JobState.JOB_STATE_CANCELLED,
            aiplatform.gapic.JobState.JOB_STATE_EXPIRED,
        }

        while True:
            job = client.get_custom_job(name=job_id)
            state = job.state
            state_name = aiplatform.gapic.JobState(state).name
            print(f"training job {job_id}: {state_name}")

            if state in terminal_states:
                break

            time.sleep(20)

        start_s = job.start_time.timestamp() if job.start_time else 0.0
        end_s = job.end_time.timestamp() if job.end_time else start_s
        duration_s = max(0.0, end_s - start_s)

        if state != succeeded:
            message = job.error.message if job.error else state_name
            raise RuntimeError(
                f"Training job ended as {state_name}: {message}"
            )

        return {
            "job_id": job.name,
            "state": state_name,
            "duration_s": duration_s,
            "output_uri": (
                job.job_spec.base_output_directory.output_uri_prefix
            ),
        }
