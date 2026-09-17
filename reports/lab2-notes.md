# Lab 2 Notes

## Managed training smoke test

- Provider: Google Cloud Vertex AI
- Region: asia-southeast1
- Compute strategy: Spot
- Instance: e2-standard-4
- Job ID: projects/764569607430/locations/asia-southeast1/customJobs/1289901686852157440
- Final state: JOB_STATE_SUCCEEDED
- Training duration: 30 seconds
- Artifacts: metrics.json and model.joblib stored in Cloud Storage
- Image was referenced using a SHA-256 digest.

## Initial submission problems

The first submissions failed because the Python import path, Vertex AI staging
bucket, and scheduling configuration were incomplete. After correcting these,
the managed training job completed successfully.
