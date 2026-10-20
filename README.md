# ITCS355 Lab 1 — Reproducible Training

> **Course materials live in [`course/`](course/README.md)** — syllabus, slides, the faculty
> specification, all five lab handouts, and the project brief. Every document is Markdown and
> renders on GitHub, diagrams included. New to the repo? Start with the
> [portability reference](course/reference/cloud-portability-reference.md).
> Keep this block when you edit the rest of this file; it is not part of the Lab 1 deliverable.

Predicting machine failure within 7 days from sensor readings. The model is not the point;
whether a stranger can reproduce it is.

> **This README is graded.** A grader with Docker and nothing else from your setup runs one
> command and compares the result against the claim below.
---

## Reproduce

```bash
make reproduce
```

expected test_roc_auc: 0.8482 ± 0.0010

Runtime: about 40 seconds on 4 cores. No cloud account or credentials needed for this command —
that is deliberate, and it is why a grader can run it.

---

## The problem

240 machines, 25 readings each, 6 sensor features, binary target `failed_within_7d` with a
positive rate near 12%.

Machines have persistent characteristics — a hot-running machine reads hot in every row. So the
train/validation/test split is **grouped by `machine_id`**: every reading from one machine lands
in exactly one partition. Splitting row-wise instead lets the model memorise the machine and
reports a validation score that will never survive production. `tests/test_data.py` asserts this
property holds, and Lab 4 turns it into a CI gate.

Bringing your own dataset is allowed. Replace `scripts/make_dataset.py`, update the schema in
`src/data.py`, and keep every test passing.

---

## Layout

```
src/          Layer 1 — provider-neutral. No SDKs, no bucket names, no absolute paths.
cloudlayer/   Layer 3 — the only place a provider SDK may be imported.
scripts/      Dataset generation, cloud check, portability audit, metric verification.
tests/        Data contract tests and split property tests.
```

`src/config.py` is the single point of environment knowledge. Everything else reads from it.
`make portability-audit` enforces the rule; it fails the build if a provider string appears in
`src/` or `tests/`.

---

## Setup

```bash
cp cloud.env.example cloud.env      # fill in, never commit
make setup
make cloud-check                    # eight slots, all PASS
make data                           # generate the dataset
make test                           # 10 tests, all passing
```

Post your `make cloud-check` output in the course channel before Session 1.

---

## What you must finish

Four `TODO` markers are left in the repo deliberately. Each is a graded decision, not busywork.

| Where | What |
|---|---|
| `requirements.txt` | Regenerate with `pip-compile --generate-hashes` |
| `Dockerfile` | Pin the base image by digest; add `--require-hashes` |
| `cloudlayer/<your provider>.py` | Implement `upload`, `download`, `push_image` |
| This README | The reproducibility trade-off question below |

Then:

```bash
make image-push        # image reaches your registry, digest-pinned
dvc init && dvc remote add -d storage ${BLOB_URI}/dvc
dvc add data/raw && dvc push
```

Run five or more tracked runs varying something meaningful — not five identical runs with
different seeds.

---

## Reproducibility trade-off

Under time pressure, I would drop deterministic seed control first.
The environment would still build from the same hashed dependencies
and digest-pinned base image, but metrics could vary between runs and
comparisons would become less reliable. I would keep dependency hashes
and the image digest because changes to packages or the base image could
silently alter the runtime without a source-code change.

---

## Notes for the grader

The training image targets linux/amd64 and runs as a non-root user.
The raw dataset is tracked with DVC and stored in the configured GCS
remote. The Docker image is stored in Google Artifact Registry and is
available using a digest-pinned reference. No cloud credentials are
stored in this repository.

### Lab 2 model promotion

Model version 1 was promoted from `candidate` to `staging` only after its lineage was recorded and it passed the registry reload check. In a real organisation, promotion should be performed by an MLOps or release owner who is independent of the model author. They should require the exact Git commit, DVC data version, MLflow run, training job, image digest, seed, validation and test metrics, seed-variance results, cost evidence, and a successful reload test before approving the promotion.

---

## Checklist before you submit

- [ ] `make reproduce` works from a fresh clone, on a machine that is not yours
- [ ] `make verify` passes against your claim line
- [ ] `make test` — all tests pass
- [ ] `make portability-audit` — clean
- [ ] Image builds for `linux/amd64` and is pushed, digest-pinned
- [ ] `dvc push` completed; a grader can `dvc pull`
- [ ] Five or more tracked runs with params, metrics, data fingerprint, and commit SHA
- [ ] All instruction blocks above have been removed (the course-materials block at the top stays)
- [ ] `git log -p | grep -i -E "secret|password|AKIA|BEGIN PRIVATE"` returns nothing

That last check is not optional. A credential in Git history is an automatic deduction in this
course, and rotating it is your responsibility, not the grader's.

## Lab 4 — Data contract incident coverage

- The schema contract test would catch an upstream producer renaming or
  removing a required sensor column before the broken data reaches training.
- The null-value test would catch a sensor pipeline that starts sending
  missing readings after a device or parsing failure.
- The plausible-range test would catch a unit error, such as temperature
  being sent in Fahrenheit instead of Celsius.
- The machine-leakage test would catch readings from the same machine being
  placed in both training and validation, which would produce an unrealistically
  high validation score.

  ## Lab 4 — Billing-free deployment substitutions

The original GCP deployment workflow using GitHub OIDC and Workload
Identity Federation is preserved in
`docs/cd-gcp-oidc-reference.yml`.

The Google Cloud billing account became inactive before the final Lab 4
deployment. With instructor approval, the following substitutions are used:

- GitHub Container Registry replaces Google Artifact Registry.
- Images remain immutable and are tagged with the tested commit SHA.
- Staging is a GitHub Actions job that runs only after successful CI on
  `main`, pulls the published image, starts it, and smoke-tests `/predict`.
- Prometheus and Grafana containers replace Cloud Monitoring.
- A scheduled GitHub Actions workflow replaces Cloud Scheduler.
- Drift alerts are still delivered to a real channel.

These substitutions preserve the CI/CD, observability, drift-detection,
alerting, and failure-evidence objectives without reopening the billing
account.

### Lab 4 drift threshold

The drift alert threshold is PSI 0.25. Comparing the reference dataset with
an unchanged copy produced PSI 0.0, while the controlled six-degree shift of
`temp_c` produced PSI 0.38333 and KS 0.24567. The threshold therefore ignores
the unchanged baseline but catches the material shift used in the exercise.
An alert is investigated as a possible upstream data problem before any
retraining decision is made.

## Lab 5 — Cloud identities and retraining plan

### Least-privilege identities

The Lab 5 design uses separate identities so that a compromise in one
component does not automatically grant control over training, serving, and
deployment.

| Identity | Required access | Reason |
|---|---|---|
| Training service account | Read objects from the training-data bucket; create model artifacts in the artifact bucket; write logs and metrics | The training job needs input data and must save its model and measurements, but it does not need deployment or registry-administration access. |
| Serving service account | Read the promoted model artifact; write serving logs and metrics | The endpoint only needs to load an approved model and publish operational telemetry. It must not modify training data, register models, or start training jobs. |
| CI identity through GitHub OIDC | Push SHA-tagged images; submit the managed pipeline; deploy to staging; act as the approved runtime service accounts | CI coordinates releases but does not receive permanent service-account keys. Permission to act as runtime identities will be scoped only to the Lab 5 accounts. |

The planned permission-removal test is to remove the training identity's
permission to create objects in the model-artifact location. The expected
result is that validation and training can run, but the training step fails
when it attempts to save the model. This experiment is pending a working
billing account and will be replaced with the actual error message and
workflow evidence after it is run.

### Scheduled retraining strategies

| Strategy | When it is right for this machine-failure system | How it can fail |
|---|---|---|
| Fixed weekly schedule | Appropriate when sensor data arrives at a predictable rate and the maintenance team needs a regular candidate-model review. | It may retrain when nothing meaningful changed, spend money unnecessarily, or react too slowly to a sudden change. |
| Data-volume threshold | Appropriate when a new candidate is useful only after enough new machine readings have accumulated, for example 10,000 validated rows. | Low-volume but important drift may never reach the threshold, while many duplicated or poor-quality rows could trigger an unnecessary run. |
| Drift-triggered | Appropriate when validated sensor distributions move persistently and the production population has genuinely changed. | A broken sensor, unit conversion error, or corrupted upstream pipeline can trigger retraining on bad data and damage a working model. |

### Selected strategy

The selected strategy is a weekly scheduled pipeline with validation and
evaluation gates. The schedule creates a candidate only after the data
contract passes, and registration occurs only when the candidate beats the
incumbent by the required evaluation margin. A drift alert starts an
investigation but does not automatically promote a new model.

The worst case is that an upstream sensor begins reporting the wrong unit.
A purely drift-triggered system could quickly retrain on corrupted data.
This design first checks schema, ranges, null rates, and data quality. If
those checks fail, the pipeline stops before training or registration.

The planned schedule is Sunday at 02:00:

```text
0 2 * * 0

### Lab 5 evaluation gate

The registration gate uses `test_roc_auc`. A candidate must score at least
0.84 and must improve over the incumbent by at least 0.002. The reproducible
Lab 1 result is approximately 0.8482 with about 0.001 variation, so the
absolute floor blocks a materially degraded model and the improvement margin
prevents ordinary training noise from being promoted.

The local proof uses the same candidate against two incumbents. Against
0.845, the improvement is approximately 0.0032 and the gate passes. Against
0.847, the improvement is only approximately 0.0012 and the gate exits with
code 1, preventing registration. Reading the incumbent metric directly from
the managed registry remains pending until the Lab 5 cloud plan is approved.