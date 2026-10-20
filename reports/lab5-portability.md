# Lab 5 Portability Review

## Current architecture

The project uses three layers. The application logic is kept under `src/`,
provider-neutral operations are defined by `cloudlayer/base.py`, and each cloud
provider is implemented separately under `cloudlayer/`. Configuration is read
from capability slots such as `BLOB_URI`, `CONTAINER_REGISTRY`,
`MODEL_REGISTRY_NAME`, and `IDENTITY_REF`.

The portability audit passes because the application and service code do not
contain provider hostnames, bucket names, or machine-specific absolute paths.
This keeps training, prediction, testing, and monitoring independent from the
selected cloud provider.

## What is portable

The dataset generation, validation tests, training code, evaluation gate,
service container, monitoring configuration, golden LLM evaluation cases, and
guardrail tests can run without changing the application code. The neutral
pipeline specification also keeps the six logical steps consistent:

`ingest -> validate -> train -> evaluate -> register -> deploy_staging`

Changing provider should therefore not require rewriting the model or service
logic.

## Where the abstraction leaks

The system is not completely portable. Each provider uses different IAM
identities, artifact URI formats, model registry APIs, endpoint invocation
formats, pipeline condition syntax, billing exports, and resource teardown
operations. A provider-specific compiler is still required to translate the
neutral pipeline into Vertex AI Pipelines, SageMaker Pipelines, or Azure ML
Pipelines.

Model registration also requires provider-specific lineage fields. For
example, the GCP implementation needs a GCS artifact URI, a digest-pinned
serving image, and Vertex AI model version metadata. These differences belong
inside `cloudlayer/`, but they cannot be removed completely.

## Honest verdict

The application layer is portable, but the managed infrastructure layer is
only partially portable. The adapter boundary reduces the amount of code that
must change, but it does not make cloud services identical.

The required second-provider upload, download, and invoke demonstration is
currently pending. The primary GCP project reports `billingEnabled=False`, and
the final provider plan is waiting for instructor confirmation. No
second-provider success is claimed in this report until it has been executed
against real cloud services.
