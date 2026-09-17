"""Lab 2 — rank tracked runs by metric AND by cost per point.

    python scripts/compare_runs.py --experiment itcs355-lab2

Writes reports/lab2-comparison.md. The cost-per-point column is what the lab is about:
the highest-scoring run is frequently not the one you should register.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow
import pandas as pd

from src import config


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    """Render a small DataFrame as Markdown without optional dependencies.

    pandas.DataFrame.to_markdown() imports the optional ``tabulate`` package.
    The comparison report is part of the core lab workflow, so generating it
    must not depend on a package that is absent from the locked environment.
    """
    columns = [str(column) for column in frame.columns]

    def row(values: list[object]) -> str:
        cells = [str(value).replace("|", "\\|") for value in values]
        return "| " + " | ".join(cells) + " |"

    lines = [
        row(columns),
        row(["---"] * len(columns)),
    ]
    lines.extend(row(list(values)) for values in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="itcs355-lab2")
    ap.add_argument("--metric", default="val_roc_auc")
    ap.add_argument("--out", type=Path, default=Path("reports/lab2-comparison.md"))
    args = ap.parse_args()

    cfg = config.load(strict=False)
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    exp = mlflow.get_experiment_by_name(args.experiment)
    if exp is None:
        print(f"No experiment named {args.experiment!r}. Run `make tune` first.")
        return 1

    runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
    if runs.empty:
        print("No runs found.")
        return 1

    metric_col = f"metrics.{args.metric}"
    cost_col = "metrics.cost_thb"
    baseline = runs[metric_col].min()

    table = pd.DataFrame({
        "run_id": runs["run_id"].str[:8],
        args.metric: runs[metric_col].round(4),
        "cost_thb": runs.get(cost_col, 0).round(4),
        "n_estimators": runs.get("params.n_estimators"),
        "max_depth": runs.get("params.max_depth"),
        "min_samples_leaf": runs.get("params.min_samples_leaf"),
    })
    gain = (table[args.metric] - baseline).clip(lower=1e-9)
    table["thb_per_point"] = (table["cost_thb"] / (gain * 100)).round(4)
    table = table.sort_values(args.metric, ascending=False)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Lab 2 — Run comparison",
        "",
        f"Experiment `{args.experiment}` · {len(table)} trials · "
        f"total spend {table['cost_thb'].sum():.4f} THB",
        "",
        "`thb_per_point` is cost per percentage point of "
        f"{args.metric} above the worst trial. Cheap improvements rank low; expensive "
        "improvements rank high, however good the headline number is.",
        "",
        dataframe_to_markdown(table),
        "",
        "## Which model did you register, and why?",
        "",
        "Justification: 200 words maximum. Address all four:",
        "",
        "1. Why this model rather than the highest-scoring one, if they differ",
        "2. The variance across seeds for your chosen configuration",
        "3. What it costs to train, and to retrain monthly",
        "4. One way this choice could be wrong",
        "",
        "An answer that only says \"highest validation score\" scores zero on this task.",
    ]
    args.out.write_text("\n".join(lines))
    print(f"wrote {args.out}  ({len(table)} trials)")
    print(table.head(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
