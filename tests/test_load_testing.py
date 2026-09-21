import csv
from pathlib import Path

import pytest

from load_testing.check_results import check_results


ROOT = Path(__file__).resolve().parents[1]


def _write_stats(path: Path, *, p95: int, p99: int, failures: int = 0) -> None:
    fields = [
        "Name",
        "Type",
        "Request Count",
        "Failure Count",
        "95%",
        "99%",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "Name": "/predict",
                "Type": "POST",
                "Request Count": "100",
                "Failure Count": str(failures),
                "95%": str(p95),
                "99%": str(p99),
            }
        )


def test_locust_payload_is_fixed_synthetic_text():
    locust_source = (ROOT / "load_testing" / "locustfile.py").read_text()
    assert 'SYNTHETIC_TEXT = "Synthetic load-test feedback' in locust_source
    assert "os.getenv" not in locust_source
    assert 'name="request_id"' not in locust_source


def test_slo_checker_accepts_results_within_thresholds(tmp_path: Path):
    path = tmp_path / "stats.csv"
    _write_stats(path, p95=420, p99=850)

    assert check_results(
        path,
        max_p95_ms=500,
        max_p99_ms=1000,
        max_error_rate=0.01,
    ) == []


def test_slo_checker_reports_latency_and_error_violations(tmp_path: Path):
    path = tmp_path / "stats.csv"
    _write_stats(path, p95=700, p99=1200, failures=3)

    violations = check_results(
        path,
        max_p95_ms=500,
        max_p99_ms=1000,
        max_error_rate=0.01,
    )

    assert len(violations) == 3
    assert any("p95_ms" in violation for violation in violations)
    assert any("p99_ms" in violation for violation in violations)
    assert any("error_rate" in violation for violation in violations)


def test_slo_checker_requires_prediction_row(tmp_path: Path):
    path = tmp_path / "stats.csv"
    path.write_text(
        "Name,Type,Request Count,Failure Count,95%,99%\n/health,GET,1,0,5,10\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="POST /predict"):
        check_results(
            path,
            max_p95_ms=500,
            max_p99_ms=1000,
            max_error_rate=0.01,
        )
