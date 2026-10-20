# Lab 5 — Cost Report

Provider plan: Google Cloud Platform  
Region: asia-southeast1  
Estimate date: 2026-10-20  
Maximum Lab 5 budget: 150 THB  
Current billing status: disabled

## 1. Estimate made before running

No Lab 5 managed cloud resources have been created yet.

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

Pending. The project currently reports `billingEnabled=False`, so no Lab 5
managed resources have been created.

## 3. The gap

Pending actual billing data.

## 4. Breakdown by component

| Component | Estimated THB | Actual THB | Notes |
|---|---:|---:|---|
| Training | 3.84 | Pending | Planned Spot compute |
| Storage | 1.00 | Pending | Pipeline and model artifacts |
| Serving | 8.00 | Pending | Short-lived staging only |
| Pipeline | 3.00 | Pending | Pass and fail-gate runs |
| Monitoring | 2.00 | Pending | Short log retention |

## 5. Cost per 1,000 predictions

Pending the approved serving configuration and measured throughput.

The provisional LLM calculation is documented separately in
`reports/lab5-token-cost.md`. It must be updated using provider-recorded
usage for all ten golden cases.

## 6. One optimisation applied

Planned optimisation: Spot training and a short-lived staging endpoint.

The endpoint will be deleted immediately after smoke testing and evidence
collection. Before-and-after cost and latency measurements will be added
after the approved managed deployment is run.
