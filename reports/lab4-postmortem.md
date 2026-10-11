# Lab 4 — Drift Incident Post-mortem

What fired: The scheduled PSI detector alerted on `temp_c` at PSI 0.38333, above the justified threshold of 0.25, with a real email notification.
True cause: This was a controlled six-degree Celsius shift injected into `temp_c`; the schema and null rate were unchanged, so the model and serving pipeline were not broken.
Retrain, roll back, or no action — and why: No model retraining is appropriate because the shift was deliberately injected; restore the original input window, and in a real incident verify and fix the upstream producer before considering retraining.
What this would have cost if unnoticed for a week: Shifted temperature inputs could distort failure probabilities, causing unnecessary maintenance work or missed machine failures.
How to prevent or detect it faster: Validate sensor units and rolling feature statistics at ingestion, and reduce the drift-check interval from 15 minutes to 5 minutes for a production-critical service.

## Evidence

- Injection started: `2026-10-11T17:32:26Z`
- Detection finished: `2026-10-11T17:32:28Z`
- Detection time: `2.0 seconds`
- Shift result: `temp_c` PSI `0.38333`, KS `0.24567`
- Alert threshold: PSI `0.25`
- Shift workflow: <https://github.com/atichatz/public_teaching_mlaiops/actions/runs/38160016090>
- Baseline workflow: <https://github.com/atichatz/public_teaching_mlaiops/actions/runs/38160439187>
- Bad-commit PR: <https://github.com/atichatz/public_teaching_mlaiops/pull/2>
