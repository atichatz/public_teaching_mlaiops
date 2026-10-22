# Lab 5 — Provisional LLM Token Cost

## Evidence status

The supplied baseline fixture contains provider-recorded token usage for eight
of the ten evaluation cases. The two custom cases, `triage-009` and
`triage-010`, do not yet have live provider usage fields. Therefore, this is a
provisional calculation and will not be presented as the final measured cost.

The final report will replace these figures after the approved Lab 5 cloud and
LLM-provider plan is confirmed.

## Current recorded usage

| Measurement | Value |
|---|---:|
| Total golden cases | 10 |
| Cases with recorded provider usage | 8 |
| Average input tokens | 416 |
| Average output tokens | 37 |

The calculation uses provider usage fields already recorded in the fixture. It
does not estimate tokens by counting words.

## Provisional cost per 1,000 requests

The current repository rate for the GCP small model is:

- Input: 8.50 THB per 1,000,000 tokens
- Output: 34.00 THB per 1,000,000 tokens

Working:

```text
((416 × 8.50) + (37 × 34.00)) / 1,000,000 × 1,000
= 4.7940 THB per 1,000 requests
