from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_disaster_recovery_runbook_covers_stateful_boundaries_and_restore_checks():
    document = (ROOT / "docs/disaster-recovery.md").read_text(encoding="utf-8")

    for required in (
        "RDS PostgreSQL",
        "S3 with versioning and KMS encryption",
        "aws rds create-db-snapshot",
        "aws rds restore-db-instance-from-db-snapshot",
        "aws s3api list-object-versions",
        "production alias",
        "/health/ready",
        "RPO",
        "RTO",
    ):
        assert required in document


def test_disaster_recovery_runbook_contains_no_secret_values():
    document = (ROOT / "docs/disaster-recovery.md").read_text(encoding="utf-8")

    assert "AWS_ACCESS_KEY_ID=" not in document
    assert "AWS_SECRET_ACCESS_KEY=" not in document
    assert "password123" not in document
    assert "-----BEGIN PRIVATE KEY-----" not in document
    assert "Authorization: Bearer" not in document
