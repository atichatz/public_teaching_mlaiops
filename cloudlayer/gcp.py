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
import re
import subprocess
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
