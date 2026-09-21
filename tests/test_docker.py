from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_dockerfile_is_non_root_and_binds_all_interfaces():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.11-slim-bookworm" in dockerfile
    assert "USER app" in dockerfile
    assert '"0.0.0.0"' in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "requirements-runtime.txt" in dockerfile
    assert "AWS_ACCESS_KEY_ID" not in dockerfile
    assert "AWS_SECRET_ACCESS_KEY" not in dockerfile


def test_dockerignore_excludes_development_and_secret_material():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    for entry in (".git", ".venv", "tests", "training", "docs", ".env"):
        assert entry in dockerignore
