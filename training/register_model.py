"""Register an MLflow run model as a candidate model version."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from typing import Any, Sequence

from training.config import load_experiment_config
from training.mlflow_tracking import resolved_tracking_uri


def register_model_version(
    *,
    run_id: str,
    model_name: str,
    tracking_uri: str,
    alias: str | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Register ``runs:/<run_id>/model`` without promoting to production."""

    try:
        import mlflow
        from mlflow import MlflowClient
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("MLflow is required for model registration") from exc

    if not run_id.strip():
        raise ValueError("run_id must not be empty")
    if not model_name.strip():
        raise ValueError("model_name must not be empty")
    if alias == "production":
        raise ValueError(
            "production alias assignment is reserved for the explicit promotion phase"
        )

    mlflow.set_tracking_uri(tracking_uri)
    registry_uri = os.getenv("MLFLOW_REGISTRY_URI")
    if registry_uri:
        mlflow.set_registry_uri(registry_uri)

    client = MlflowClient(tracking_uri=tracking_uri)
    run = client.get_run(run_id)
    model_uri = f"runs:/{run_id}/model"
    version = mlflow.register_model(model_uri, model_name)

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        current = client.get_model_version(model_name, version.version)
        if current.status == "READY":
            break
        time.sleep(1)
    else:
        raise TimeoutError(
            f"model version {model_name}/{version.version} did not become READY"
        )

    tags = {
        "lifecycle_status": "candidate",
        "source_run_id": run_id,
        "git_commit": run.data.tags.get("git_commit", "unknown"),
        "dataset_revision": run.data.tags.get("dataset_revision", "unknown"),
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    for key, value in tags.items():
        client.set_model_version_tag(model_name, version.version, key, value)

    if alias:
        client.set_registered_model_alias(model_name, alias, version.version)

    return {
        "model_name": model_name,
        "version": str(version.version),
        "source": model_uri,
        "run_id": run_id,
        "lifecycle_status": "candidate",
        "alias": alias,
        "tracking_uri": tracking_uri,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="training/config.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model-name")
    parser.add_argument(
        "--alias",
        default="candidate",
        help="optional non-production alias; production is disallowed here",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_experiment_config(args.config)
    result = register_model_version(
        run_id=args.run_id,
        model_name=args.model_name or config.mlflow.registered_model_name,
        tracking_uri=resolved_tracking_uri(config),
        alias=args.alias,
    )
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
