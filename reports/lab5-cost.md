# Lab 5 — Cost Report

Provider plan: Google Cloud Platform  
Region: asia-southeast1  
Estimate date: 2026-10-20  
Maximum Lab 5 budget: 150 THB  
Current billing status: enabled with budget alerts and a 100 THB Vertex AI cap

## 1. Estimate made before running

Estimated total Lab 5 spend: **30.00 THB**

| Component | Planned usage | Estimated THB |
|---|---:|---:|
| Spot training | e2-standard-4 equivalent for approximately 2 hours | 3.84 |
| Staging serving | Short-lived staging endpoint | 8.00 |
| Storage | Pipeline, model, and report artifacts | 1.00 |
| Pipeline orchestration | Pass run and deliberate fail-gate run | 3.00 |
| Monitoring and logging | Short retention for Lab 5 | 2.00 |
| LLM evaluation | Limited live calls to record usage fields | 1.00 |
| Second-provider portability test | Upload, download, and invoke | 4.00 |
| Contingency | Debugging time and price variation | 7.16 |
| **Total** |  | **30.00** |

The training estimate uses the repository starting rate of 6.40 THB/hour and a 30% Spot factor, giving approximately 1.92 
THB/hour. The final report will verify all rates against the approved provider and region before they are presented as 
current prices.

This estimate was written and committed before the first Lab 5 managed
pipeline execution.

## 2. Actual, from billing filtered by tag

The managed fail-gate and pass-gate runs were executed on 21–22 October 2026.
Cloud Billing had not yet posted final tagged charges when the run evidence was
collected, so this report does not invent an "actual" number from list prices.
The final billed amount must be copied from the Billing report after its
reporting delay, filtered to project `itcs355-6688193` and the Lab 5 execution
window. The 100 THB Vertex AI cap and budget alerts remained active throughout.

Operational evidence confirms that the only real-time endpoint was deleted
immediately after three successful smoke predictions; the post-teardown
endpoint list was empty. Pipeline state, metrics, smoke output, and teardown
evidence are in `reports/lab5-managed-gate-pass.txt`.

## 3. The gap

The numerical estimate-versus-actual gap will be calculated when Cloud Billing
finishes posting the charges. The principal source of an upward gap is the
additional diagnostic pipeline executions required to correct container file
permissions, tracking storage, and the exact KFP gate output. The short-lived
endpoint and layer-cached image rebuilds reduce the serving and build portions
of that gap.

## 4. Breakdown by component

| Component | Estimated THB | Actual THB | Notes |
|---|---:|---:|---|
| Training | 3.84 | Awaiting billing post | Managed training plus diagnostic reruns |
| Storage | 1.00 | Awaiting billing post | Pipeline, model, metrics, and report artifacts |
| Serving | 8.00 | Awaiting billing post | One staging endpoint, deleted after smoke test |
| Pipeline | 3.00 | Awaiting billing post | Deliberate fail gate, diagnostics, and final pass |
| Monitoring | 2.00 | Awaiting billing post | Vertex job and endpoint logs |

## 5. Cost per 1,000 predictions

Only three smoke requests were sent before teardown, so extrapolating those
fixed provisioning charges to a cost per 1,000 predictions would be misleading.
For this low request volume, scheduled batch inference or a scale-to-zero
service is cheaper than an always-on Vertex endpoint.

The provisional LLM calculation is documented separately in
`reports/lab5-token-cost.md`. It must be updated using provider-recorded
usage for all ten golden cases.

## 6. One optimisation applied

The staging endpoint was deleted synchronously immediately after three smoke
requests, and a follow-up list confirmed that no endpoint remained. This avoids
paying for an idle always-on replica. Image layers were also reused during
diagnostic rebuilds, and immutable digests prevented unnecessary ambiguity or
rebuilds during the final run.
