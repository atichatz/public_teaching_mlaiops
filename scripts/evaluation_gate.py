"""Lab 5 — the registration gate.

Compares a candidate against the currently registered production model. Exits non-zero
when the candidate should NOT be registered, which is what makes the pipeline condition
real rather than decorative.

    python scripts/evaluation_gate.py --metrics reports/metrics.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The reproducible Lab 1 model scores about 0.8482 test ROC AUC with
# approximately +/-0.001 variation. The absolute floor of 0.84 blocks a
# materially degraded model. The 0.002 improvement requirement is twice the
# observed variation, so ordinary training noise is not promoted.
MIN_ABSOLUTE = 0.84
MIN_IMPROVEMENT = 0.002


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--metric", default="test_roc_auc")
    ap.add_argument("--incumbent", type=float, default=None,
                    help="current production score; omit to read from the registry")
    ap.add_argument("--decision-out", type=Path, default=None,
                    help="optional file for writing the gate decision: pass or fail")
    args = ap.parse_args()

    def finish(decision: str, exit_code: int) -> int:
        if args.decision_out:
            args.decision_out.parent.mkdir(parents=True, exist_ok=True)
            args.decision_out.write_text(decision + "\n")
            print(f"wrote gate decision={decision} to {args.decision_out}")
        return exit_code

    payload = json.loads(args.metrics.read_text())
    candidate = float(payload[args.metric])
    print(f"candidate {args.metric} = {candidate:.4f}")

    if candidate < MIN_ABSOLUTE:
        print(f"GATE FAIL  below absolute floor {MIN_ABSOLUTE}")
        return finish("fail", 1)

    incumbent = args.incumbent
    if incumbent is None:
        # TODO(Lab 5): read the production version's metric from the registry instead of
        # assuming there is no incumbent. A first run legitimately has none.
        print("no incumbent supplied — treating as first registration")
        print("GATE PASS")
        return finish("pass", 0)

    delta = candidate - incumbent
    print(f"incumbent {incumbent:.4f}  delta {delta:+.4f}  required {MIN_IMPROVEMENT:+.4f}")
    if delta < MIN_IMPROVEMENT:
        print("GATE FAIL  improvement within noise; not registering")
        return finish("fail", 1)

    print("GATE PASS")
    return finish("pass", 0)


if __name__ == "__main__":
    raise SystemExit(main())