"""Lab 2 — prove the registered model can be reloaded by version, from the registry.

    python scripts/reload_check.py --name itcs355-<studentid> --version 3

This is the lab's quiet test. Models that cannot be reloaded six months later are the
commonest form of dead work in industry, and the cause is nearly always a serialization
assumption: a custom class that no longer exists, a library version that moved, a
preprocessing step that only ever lived in a notebook.

Loading from a local file instead of the registry defeats the purpose and is checked.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib

from cloudlayer.factory import get_adapter
from src import config, data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="registered model name")
    ap.add_argument("--version", help="registered model version")
    ap.add_argument("--rows", type=int, default=5)
    args = ap.parse_args()

    cfg = config.load()
    name = args.name or cfg.model_registry_name
    version_file = cfg.reports_dir / "lab2-registry-version.txt"
    version = args.version or version_file.read_text().strip()
    adapter = get_adapter(cfg)
    registered = adapter.resolve_registered_model(name, version)
    required = {
        "git_commit",
        "data_version",
        "mlflow_run_id",
        "training_job_id",
        "image_digest",
        "seed",
        "metric_val",
        "metric_test",
    }
    missing = sorted(required - registered["metadata"].keys())
    if missing:
        raise RuntimeError("Registered version is missing lineage: " + ", ".join(missing))

    print(f"loading {registered['name']}")
    print(f"aliases: {', '.join(registered['aliases'])}")
    model_uri = registered["artifact_uri"].rstrip("/") + "/model.joblib"
    with tempfile.TemporaryDirectory() as temporary_dir:
        local_model = Path(temporary_dir) / "model.joblib"
        adapter.download(model_uri, str(local_model))
        model = joblib.load(local_model)

    df = data.load_raw(cfg.raw_path)
    _, _, test_df = data.split(df, seed=20260101)
    sample = test_df.head(args.rows)
    preds = model.predict_proba(sample[data.FEATURES])[:, 1]

    for rid, p in zip(sample[data.ID], preds):
        print(f"  reading {rid}: p(failure)={p:.4f}")
    print("\nPASS  model reloaded from the registry and scored rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
