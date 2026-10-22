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

The second-provider swap check selected Azure while GCP remained the primary
provider. The same application-facing calls reached the Azure adapter without
changes under `src/`, but `upload`, `download`, and `invoke` all reported
`NOT IMPLEMENTED`; the check exited with code 1. This is a useful failed
demonstration rather than a portability claim. Its output is recorded in
`reports/lab5-second-provider-attempt.txt`.

`invoke` would be the hardest method to port. Object upload and download mostly
require URI parsing and authentication changes, whereas online invocation also
depends on model registration, endpoint provisioning, readiness behaviour,
request envelopes, response formats, traffic routing, and provider-specific
identity propagation. Hiding all of those behind one method would either leak
provider concepts into the interface or reduce the interface to a lowest
common denominator.

A minimal, tested Azure implementation of upload, download, and invocation is
estimated at five to eight engineering days: one to two days for identity and
storage, three to four for model registration and endpoint lifecycle, and one
to two for integration tests and teardown. A production migration would take
longer because pipeline compilation, monitoring, billing attribution, and
incident procedures are also provider-specific.

The verdict is **no: completing a second managed-cloud implementation is not
worth the cost for this single workload today**. Keeping the provider-neutral
training and service code, the small adapter boundary, and portability tests is
valuable. Building and operating a second full control plane before there is a
business or resilience requirement would add more maintenance risk than it
removes. The failed swap check makes that boundary explicit instead of claiming
portability that has not been demonstrated.
