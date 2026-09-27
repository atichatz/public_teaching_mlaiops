// ITCS355 Lab 3 — load test.
//
//   k6 run -e TARGET=https://<endpoint>/predict -e VUS=10 loadtest/k6.js
//
// Run this at THREE concurrency levels (suggested 1, 10, 50) and record p50, p95, p99,
// throughput, and error rate for each. Commit the results in reports/lab3-load.md.
//
// An uncommitted load test is not evidence.

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const latency = new Trend('predict_latency_ms');
const failures = new Rate('predict_failures');

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || '60s',

  summaryTrendStats: [
    'avg',
    'p(50)',
    'p(95)',
    'p(99)',
    'max',
  ],

  thresholds: {
    // The p95 target of 200 ms was declared before measurement.
    'predict_latency_ms': ['p(95)<200'],
    'predict_failures': ['rate<0.01'],
  },
};

const padBytes = Number(__ENV.PAD_BYTES || 0);

const payload = JSON.stringify({
  temp_c: 78.4,
  vibration_mm_s: 3.1,
  pressure_kpa: 315.2,
  hours_since_service: 4200,
  load_pct: 68.0,
  ambient_humidity: 55.0,
}) + ' '.repeat(padBytes);

export default function () {
  const res = http.post(__ENV.TARGET, payload, {
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${__ENV.TOKEN}`,
  },
});
  latency.add(res.timings.duration);
  failures.add(res.status !== 200);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'probability present': (r) => r.status === 200 && r.json('probability') !== undefined,
    'version reported': (r) => r.status === 200 && r.json('model_version') !== undefined,  });
}

if (!__ENV.TARGET) {
  throw new Error('TARGET is required');
}

if (!__ENV.TOKEN) {
  throw new Error('TOKEN is required');
}
