"""Run a checkpointed hyperparameter study on managed Spot compute."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow

from cloudlayer.factory import get_adapter
from scripts.train_remote import gcs_mount_path
from src import config, costs, seeds
from src.train import dvc_data_hash, git_commit
from src.tune import SEARCH_SPACE, grid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--instance", default="e2-standard-4")
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--budget-thb", type=float, default=150.0)
    parser.add_argument("--seed", type=int, default=seeds.DEFAULT_SEED)
    parser.add_argument("--experiment", default="itcs355-lab2")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("reports/tune_checkpoint.json"),
    )
    return parser.parse_args()


def load_checkpoint(path: Path, adapter, remote_uri: str) -> dict:
    if path.exists():
        print(f"resuming from local checkpoint: {path}")
        return json.loads(path.read_text())

    try:
        adapter.download(remote_uri, str(path))
        print(f"resuming from cloud checkpoint: {remote_uri}")
        return json.loads(path.read_text())
    except Exception:
        print("no previous checkpoint; starting a new study")
        return {
            "completed": [],
            "records": [],
            "spent_thb": 0.0,
        }


def save_checkpoint(path: Path, state: dict, adapter) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
    return adapter.upload(str(path), "lab2/tune/checkpoint.json")


def main() -> int:
    args = parse_args()
    cfg = config.load()
    adapter = get_adapter(cfg)

    if "@sha256:" not in args.image_uri:
        raise ValueError(
            "--image-uri must be digest-pinned and contain @sha256:"
        )

    blob_root = cfg.blob_uri.rstrip("/")
    checkpoint_uri = f"{blob_root}/lab2/tune/checkpoint.json"
    state = load_checkpoint(args.checkpoint, adapter, checkpoint_uri)

    candidates = grid(SEARCH_SPACE)[: args.trials]
    spot_rate = costs.hourly_rate(
        cfg.provider,
        args.instance,
        spot=True,
    )

    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    mlflow.set_experiment(args.experiment)

    print(f"candidate count: {len(candidates)}")
    print(f"Spot rate: {spot_rate:.4f} THB/hour")
    print(f"current spend: {state['spent_thb']:.4f} THB")

    for index, params in enumerate(candidates, start=1):
        trial_key = json.dumps(
            {"params": params, "seed": args.seed},
            sort_keys=True,
        )

        if trial_key in state["completed"]:
            print(f"trial {index}: already completed; skipping")
            continue

        # Reserve an estimated ten minutes before starting a new trial.
        projected_cost = spot_rate * (10.0 / 60.0)
        if state["spent_thb"] + projected_cost > args.budget_thb:
            print(
                "BUDGET STOP: projected trial would exceed "
                f"{args.budget_thb:.2f} THB"
            )
            break

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_name = f"itcs355-lab2-t{index:02d}-{timestamp}"
        output_uri = f"{blob_root}/lab2/tune/{job_name}"
        metrics_uri = f"{output_uri}/metrics.json"
        model_uri = f"{output_uri}/model.joblib"
        data_uri = f"{blob_root}/lab2/data/sensors.csv"

        container_args = [
            "--experiment",
            "itcs355-lab2-remote",
            "--run-name",
            job_name,
            "--data-path",
            gcs_mount_path(data_uri),
            "--metrics-out",
            gcs_mount_path(metrics_uri),
            "--model-out",
            gcs_mount_path(model_uri),
            "--seed",
            str(args.seed),
            "--n-estimators",
            str(params["n_estimators"]),
            "--max-depth",
            str(params["max_depth"]),
            "--min-samples-leaf",
            str(params["min_samples_leaf"]),
        ]

        submit_args = {
            "job_name": job_name,
            "instance": args.instance,
            "output_uri": output_uri,
            "container_args": container_args,
            "env": {
                "GIT_COMMIT": git_commit(),
                "DVC_DATA_HASH": dvc_data_hash(),
                "MLFLOW_TRACKING_URI": "sqlite:////tmp/mlflow.db",
            },
        }

        print()
        print(f"submitting trial {index}/{len(candidates)}")
        print(f"parameters: {params}")
        print(f"output: {output_uri}")

        job_id = adapter.submit_training(
            args.image_uri,
            submit_args,
        )
        result = adapter.wait_training(job_id)

        local_metrics = (
            Path("reports")
            / "tune"
            / f"trial-{index:02d}-metrics.json"
        )
        adapter.download(metrics_uri, str(local_metrics))
        metrics = json.loads(local_metrics.read_text())

        duration_s = float(result["duration_s"])
        trial_cost = (duration_s / 3600.0) * spot_rate
        state["spent_thb"] += trial_cost

        with mlflow.start_run(run_name=job_name) as run:
            mlflow.log_params(
                {
                    **params,
                    "seed": args.seed,
                    "instance": args.instance,
                    "compute": "spot",
                }
            )
            mlflow.log_metrics(
                {
                    "val_roc_auc": metrics["val_roc_auc"],
                    "val_pr_auc": metrics["val_pr_auc"],
                    "test_roc_auc": metrics["test_roc_auc"],
                    "test_pr_auc": metrics["test_pr_auc"],
                    "duration_s": duration_s,
                    "cost_thb": trial_cost,
                }
            )
            mlflow.set_tags(
                {
                    "git_commit": git_commit(),
                    "data_version": dvc_data_hash(),
                    "training_job_id": job_id,
                    "image_digest": args.image_uri.split("@", 1)[1],
                    "model_uri": model_uri,
                    "lab": "2",
                }
            )
            run_id = run.info.run_id

        record = {
            "trial": index,
            "params": params,
            "seed": args.seed,
            "run_id": run_id,
            "training_job_id": job_id,
            "model_uri": model_uri,
            "metrics_uri": metrics_uri,
            "image_uri": args.image_uri,
            "duration_s": duration_s,
            "cost_thb": trial_cost,
            **metrics,
        }

        state["completed"].append(trial_key)
        state["records"].append(record)

        uploaded = save_checkpoint(
            args.checkpoint,
            state,
            adapter,
        )

        print(
            f"trial {index} complete: "
            f"val_roc_auc={metrics['val_roc_auc']:.4f}, "
            f"cost={trial_cost:.4f} THB"
        )
        print(f"checkpoint: {uploaded}")

    print()
    print(
        f"completed {len(state['completed'])}/{len(candidates)} trials"
    )
    print(
        f"estimated spend: {state['spent_thb']:.4f}/"
        f"{args.budget_thb:.2f} THB"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
