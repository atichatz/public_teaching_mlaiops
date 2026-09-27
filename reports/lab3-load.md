# Lab 3 Load Test Report

## Test configuration

- Cloud provider: Google Cloud Vertex AI
- Region: asia-southeast1
- Baseline instance: n1-standard-2
- Comparison instance: n1-standard-4
- Minimum replicas: 1
- Maximum replicas: 1
- Endpoint ID: 8589853228139544576
- Model registry version: 1
- Serving model version: 2
- Test duration: 60 seconds per concurrency level
- Latency target declared before measurement: p95 < 200 ms
- Error-rate target: < 1%
- Test date: 2026-09-26

The p95 latency target was defined before running the measured load tests. Cold-start latency was measured separately and was not included in the steady-state load-test results.

## Results

| VUs | Requests/s | p50 ms | p95 ms | p99 ms | Error rate | Target met |
|---:|---:|---:|---:|---:|---:|:---:|
| 1 | 6.632 | 140.977 | 224.906 | 330.624 | 0.00% | No |
| 10 | 30.178 | 309.437 | 586.526 | 724.859 | 0.00% | No |
| 50 | 22.883 | 2120.469 | 3243.532 | 3587.073 | 0.00% | No |

## Baseline finding

The n1-standard-2 configuration did not meet the declared p95 target of 200 ms, even at the lowest tested concurrency of 1 VU. Therefore, the breaking concurrency for this configuration is at or below 1 VU.

Throughput increased from 6.632 requests/s at 1 VU to 30.178 requests/s at 10 VUs, but decreased to 22.883 requests/s at 50 VUs. At 50 VUs, p50 increased to 2.12 seconds and p95 increased to 3.24 seconds, indicating queueing and instance saturation rather than request errors.

## Cold-start result

The first request after deployment completed successfully in 0.279 seconds. This result was recorded separately and was not included in the p50, p95, or p99 steady-state latency results.

## Instance-size experiment

| Instance | VUs | RPS | p50 ms | p95 ms | p99 ms | Error rate | Target met |
|---|---:|---:|---:|---:|---:|---:|:---:|
| n1-standard-2 | 1 | 6.632 | 140.977 | 224.906 | 330.624 | 0.00% | No |
| n1-standard-2 | 10 | 30.178 | 309.437 | 586.526 | 724.859 | 0.00% | No |
| n1-standard-2 | 50 | 22.883 | 2120.469 | 3243.532 | 3587.073 | 0.00% | No |
| n1-standard-4 | 1 | 7.392 | 134.046 | 172.406 | 193.885 | 0.00% | Yes |
| n1-standard-4 | 10 | 38.130 | 251.600 | 401.288 | 498.491 | 0.00% | No |
| n1-standard-4 | 50 | 33.826 | 1136.292 | 1998.259 | 5902.238 | 0.00% | No |

## Instance-size finding

The n1-standard-4 instance was tested using the same payload, endpoint,
test duration, and concurrency levels as the n1-standard-2 baseline.

At 1 VU, the p95 latency decreased from 224.906 ms to 172.406 ms, and
the larger instance met the declared p95 target. At 10 VUs, the p95
latency decreased from 586.526 ms to 401.288 ms, but it was still above
the target. At 50 VUs, the p95 latency decreased from 3243.532 ms to
1998.259 ms.

The larger instance improved both latency and throughput at all three
concurrency levels. However, it only met the p95 target at 1 VU. This
shows that increasing the instance size improved performance, but it
did not prevent queueing when concurrency became high.

## Breaking-point experiment

| VUs | RPS | p50 ms | p95 ms | p99 ms | Error rate | Target met |
|---:|---:|---:|---:|---:|---:|:---:|
| 2 | 13.846 | 137.655 | 194.958 | 281.840 | 0.00% | Yes |
| 3 | 20.569 | 140.807 | 193.356 | 302.385 | 0.00% | Yes |
| 4 | 25.930 | 148.128 | 212.974 | 319.874 | 0.00% | No |
| 5 | 29.279 | 161.596 | 225.796 | 308.931 | 0.00% | No |
| 8 | 37.121 | 205.980 | 317.546 | 421.193 | 0.00% | No |

## Breaking-point finding

The n1-standard-4 instance met the p95 latency target at 3 VUs,
with a p95 latency of 193.356 ms. At 4 VUs, the p95 latency increased
to 212.974 ms and crossed the declared target of 200 ms.

Therefore, the first failing concurrency, or breaking point, was
4 VUs. The error rate remained 0%, which means the system first showed
performance degradation through increased latency rather than failed
requests.

## Payload-size experiment

The payload-size experiment used 1 VU and a duration of 30 seconds.
Whitespace was added after the valid JSON body so that the request
schema and prediction values remained unchanged.

| Padding size | RPS | p50 ms | p95 ms | p99 ms | Error rate |
|---:|---:|---:|---:|---:|---:|
| 0 bytes | 6.905 | 133.755 | 217.590 | 402.827 | 0.00% |
| 10 KB | 7.197 | 125.140 | 186.891 | 286.380 | 0.46% |
| 100 KB | 7.011 | 133.471 | 199.903 | 299.746 | 0.47% |
| 1 MB | 0.919 | 1027.752 | 1241.997 | 1996.076 | 3.57% |

## Payload-size finding

The results for payload sizes between 0 bytes and 100 KB were
relatively similar, although there was some variation between the
test runs. The p95 latency remained close to 200 ms, and the error
rate remained below 1%.

The 1 MB payload produced a clear performance decrease. Its p95
latency increased to 1241.997 ms, while throughput decreased to
0.919 requests per second. The error rate also increased to 3.57%,
which was above the declared error-rate target. This indicates that
network transfer and request serialization became important when the
payload size reached approximately 1 MB in this experiment.

## Batch-size experiment

The batch experiment compared 100 sequential requests to `/predict`
with one request containing 100 rows sent to `/predict/batch`. Both
tests used the same n1-standard-4 instance, model artifact, input
values, and Vertex AI endpoint.

| Mode | HTTP requests | Predictions | Total time s | Predictions/s | ms/prediction |
|---|---:|---:|---:|---:|---:|
| Single | 100 | 100 | 78.330 | 1.277 | 783.297 |
| Batch | 1 | 100 | 0.863 | 115.928 | 8.626 |

The batch request was 90.81 times faster than 100 sequential single
requests. This improvement mainly came from reducing the number of
network round trips from 100 requests to one request.

## Canary and rollback experiment

A second serving model version added a controlled 150 ms delay to each
prediction. It used the same model artifact and serving image as the
baseline. The purpose was to create a small but measurable serving
degradation.

The detection rule was declared before measurement. Degradation would
be detected when p95 latency reached at least 200 ms or the error rate
reached at least 1%.

Traffic was split between the baseline and canary deployments at
90% and 10%, respectively.

| Metric | Canary period |
|---|---:|
| p50 latency | 143.657 ms |
| p95 latency | 218.347 ms |
| p99 latency | 1142.826 ms |
| Error rate | 0.00% |
| Requests | 885 |
| Detection time | 71 seconds |

The p95 latency crossed the declared 200 ms threshold and revealed the
degradation. The error rate remained 0%, showing that the problem was
a performance degradation rather than request failure.

The first canary attempt used a smaller delay and did not cross the
declared threshold. It was retained as a failed detection attempt
instead of being reported as a successful detection.

After detection, traffic was changed from 90/10 back to 100% baseline.
The final rollback completed in 9 seconds. Timestamped traffic evidence
is stored in the reports directory. A smoke test after rollback
confirmed that the baseline continued to serve predictions correctly.

With a 50/50 split, degradation would probably have been detected
faster because half of the requests would reach the canary. However,
the blast radius would be five times larger than the 10% canary because
more users would receive responses from the degraded version.

## Cost per 1,000 predictions

The selected configuration was an n1-standard-4 instance at 3 VUs.
The measured throughput was 20.569 requests per second, while the p95
latency was 193.356 ms, which remained below the declared 200 ms target.

The course cost estimate for n1-standard-4 was 7.60 THB per hour.
The calculation assumed 25% average utilisation.

Cost per 1,000 predictions:

7.60 / (20.569 x 3600 x 0.25) x 1000 = 0.411 THB

Therefore, the estimated cost was approximately 0.411 THB per 1,000
predictions. This estimate is sensitive to utilisation because the
endpoint is billed while it is running, even when no requests arrive.

## Online versus batch cost

Assuming a batch job uses the same n1-standard-4 instance for a minimum
of 30 minutes, one batch run would cost approximately 3.80 THB. At the
measured batch throughput of 115.928 predictions per second, one
30-minute run could process approximately 208,670 predictions.

A continuously warm endpoint would cost approximately 182.40 THB per
day. Under these assumptions, batch inference would remain cheaper for
up to 47 half-hour batch runs, or approximately 9.81 million predictions
per day. At 48 full runs per day, the compute cost would equal the cost
of keeping the endpoint warm.
