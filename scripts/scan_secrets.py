"""Scan the complete Git history for likely committed credentials."""

from __future__ import annotations

import re
import subprocess
import sys


PATTERNS = {
    "private key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "GitHub token": re.compile(
        r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{30,}\b"
    ),
    "Google OAuth token": re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}\b"),
    "assigned secret": re.compile(
        r"""(?ix)
        \b(password|passwd|client_secret|api_key|access_token)
        \s*[:=]\s*
        ["'][^"'<>]{8,}["']
        """
    ),
}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def main() -> int:
    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        print(
            "FAIL repository is shallow. "
            "GitHub Actions must use fetch-depth: 0."
        )
        return 1

    history = git(
        "log",
        "--all",
        "-p",
        "--no-ext-diff",
        "--no-color",
    )

    findings: list[str] = []

    for name, pattern in PATTERNS.items():
        match = pattern.search(history)
        if match:
            findings.append(name)

    if findings:
        print("FAIL possible credential found in Git history:")
        for finding in findings:
            print(f"  - {finding}")
        print("Review and rotate real credentials before submission.")
        return 1

    print("PASS no likely credentials found in full Git history")
    return 0


if __name__ == "__main__":
    sys.exit(main())
