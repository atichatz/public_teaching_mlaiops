"""Send a Lab 4 drift alert through an SMTP account configured in secrets."""
from __future__ import annotations

import argparse
import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def elapsed_seconds(start: str, end: str) -> float:
    started = datetime.fromisoformat(start.replace("Z", "+00:00"))
    finished = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return round((finished - started).total_seconds(), 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("reports/drift.json"))
    parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()

    results = json.loads(args.report.read_text(encoding="utf-8"))
    breached = [row for row in results if float(row["psi"]) >= args.threshold]
    if not breached:
        print("No drift threshold breach; no email sent.")
        return 0

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    username = required_env("SMTP_USERNAME")
    password = required_env("SMTP_APP_PASSWORD")
    recipient = required_env("ALERT_TO")
    started = required_env("INJECTION_STARTED_AT")
    finished = required_env("DETECTION_FINISHED_AT")
    duration = elapsed_seconds(started, finished)

    lines = [
        "ITCS355 Lab 4 drift alert",
        "",
        f"Threshold: PSI >= {args.threshold}",
        f"Injection started: {started}",
        f"Detection finished: {finished}",
        f"Detection time: {duration} seconds",
        "",
        "Breached features:",
    ]
    lines.extend(
        f"- {row['feature']}: PSI={row['psi']}, KS={row['ks_statistic']}, "
        f"mean {row['ref_mean']} -> {row['cur_mean']}"
        for row in breached
    )
    lines.extend(
        [
            "",
            "Investigate the upstream data pipeline before retraining.",
            f"GitHub run: {os.environ.get('GITHUB_SERVER_URL', '')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/"
            f"{os.environ.get('GITHUB_RUN_ID', '')}",
        ]
    )

    message = EmailMessage()
    message["Subject"] = f"[ITCS355 Lab 4] Drift detected in {breached[0]['feature']}"
    message["From"] = username
    message["To"] = recipient
    message.set_content("\n".join(lines))

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)

    print(f"Drift alert sent to {recipient}; detection time {duration} seconds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
