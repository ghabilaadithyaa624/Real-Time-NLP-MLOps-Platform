"""Check Locust CSV output against explicit API SLO thresholds."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _number(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    if not raw:
        raise ValueError(f"Locust CSV is missing a value for {field}")
    return float(raw)


def check_results(
    path: Path,
    *,
    max_p95_ms: float,
    max_p99_ms: float,
    max_error_rate: float,
) -> list[str]:
    """Return violations for the prediction row; an empty list means pass."""

    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    row = next(
        (
            item
            for item in rows
            if item.get("Name") == "/predict" and item.get("Type") == "POST"
        ),
        None,
    )
    if row is None:
        raise ValueError("Locust CSV does not contain a POST /predict row")

    requests = _number(row, "Request Count")
    failures = _number(row, "Failure Count")
    p95 = _number(row, "95%")
    p99 = _number(row, "99%")
    error_rate = failures / requests if requests else 1.0

    violations: list[str] = []
    if p95 > max_p95_ms:
        violations.append(f"p95_ms={p95:g} exceeds {max_p95_ms:g}")
    if p99 > max_p99_ms:
        violations.append(f"p99_ms={p99:g} exceeds {max_p99_ms:g}")
    if error_rate > max_error_rate:
        violations.append(
            f"error_rate={error_rate:.4%} exceeds {max_error_rate:.4%}"
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--max-p95-ms", type=float, default=500.0)
    parser.add_argument("--max-p99-ms", type=float, default=1000.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    args = parser.parse_args()

    violations = check_results(
        args.csv_path,
        max_p95_ms=args.max_p95_ms,
        max_p99_ms=args.max_p99_ms,
        max_error_rate=args.max_error_rate,
    )
    if violations:
        for violation in violations:
            print(f"SLO FAILED: {violation}")
        return 1
    print(
        "SLO PASSED: "
        f"p95<={args.max_p95_ms:g}ms, "
        f"p99<={args.max_p99_ms:g}ms, "
        f"errors<={args.max_error_rate:.4%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
