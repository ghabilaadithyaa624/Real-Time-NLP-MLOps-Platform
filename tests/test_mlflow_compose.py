from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _compose():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_mlflow_profile_separates_postgres_metadata_from_s3_artifacts():
    services = _compose()["services"]

    assert services["postgres"]["image"] == "postgres:16.4-alpine"
    assert services["minio"]["image"] == "minio/minio:RELEASE.2024-12-18T13-15-44Z"
    assert services["mlflow"]["image"] == "ghcr.io/mlflow/mlflow:v2.19.0"
    assert services["postgres"]["profiles"] == ["mlflow"]
    assert services["minio"]["profiles"] == ["mlflow"]
    assert services["mlflow"]["profiles"] == ["mlflow"]

    mlflow_command = " ".join(services["mlflow"]["command"])
    assert "postgresql+psycopg2://" in mlflow_command
    assert "--default-artifact-root" in mlflow_command
    assert "s3://" in mlflow_command
    assert services["mlflow"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert (
        services["mlflow"]["depends_on"]["mlflow-bucket-init"]["condition"]
        == "service_completed_successfully"
    )


def test_mlflow_credentials_are_required_at_runtime_not_committed():
    services = _compose()["services"]
    postgres_env = services["postgres"]["environment"]
    minio_env = services["minio"]["environment"]

    assert ":?Set MLFLOW_POSTGRES_PASSWORD" in postgres_env["POSTGRES_PASSWORD"]
    assert ":?Set MINIO_ROOT_USER" in minio_env["MINIO_ROOT_USER"]
    assert ":?Set MINIO_ROOT_PASSWORD" in minio_env["MINIO_ROOT_PASSWORD"]

    serialized = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "password123" not in serialized
    assert "AWS_SECRET_ACCESS_KEY: secret" not in serialized


def test_mlflow_data_volumes_are_ignored():
    compose = _compose()
    volumes = compose["volumes"]
    assert "postgres-data" in volumes
    assert "minio-data" in volumes

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "postgres-data/" in gitignore
    assert "minio-data/" in gitignore
