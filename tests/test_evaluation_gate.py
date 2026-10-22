"""Regression tests for the managed-pipeline gate output contract."""
from __future__ import annotations

import json
import subprocess
import sys


def test_pass_decision_has_no_trailing_newline(tmp_path):
    metrics = tmp_path / "metrics.json"
    decision = tmp_path / "decision.txt"
    metrics.write_text(json.dumps({"test_roc_auc": 0.8465}))

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/evaluation_gate.py",
            "--metrics",
            str(metrics),
            "--incumbent",
            "0.844",
            "--decision-out",
            str(decision),
        ],
        check=False,
    )

    assert completed.returncode == 0
    assert decision.read_bytes() == b"pass"


def test_fail_decision_has_no_trailing_newline(tmp_path):
    metrics = tmp_path / "metrics.json"
    decision = tmp_path / "decision.txt"
    metrics.write_text(json.dumps({"test_roc_auc": 0.8465}))

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/evaluation_gate.py",
            "--metrics",
            str(metrics),
            "--incumbent",
            "0.845",
            "--decision-out",
            str(decision),
        ],
        check=False,
    )

    assert completed.returncode == 1
    assert decision.read_bytes() == b"fail"
