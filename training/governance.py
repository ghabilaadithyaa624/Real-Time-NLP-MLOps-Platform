"""MLflow model-governance decisions and alias transitions."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from training.utils import json_safe


class GovernanceError(RuntimeError):
    """Raised when a governance operation cannot safely proceed."""


def _require_mlflow() -> tuple[Any, Any]:
    try:
        import mlflow
        from mlflow import MlflowClient
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise GovernanceError("MLflow is required for governance operations") from exc
    return mlflow, MlflowClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_report(path: str | Path) -> tuple[dict[str, Any], str]:
    report_path = Path(path)
    if not report_path.exists():
        raise GovernanceError(f"evaluation report does not exist: {report_path}")
    try:
        raw = report_path.read_bytes()
        report = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"could not read evaluation report: {report_path}") from exc
    if not isinstance(report, dict):
        raise GovernanceError("evaluation report root must be an object")
    return report, hashlib.sha256(raw).hexdigest()


def _version_tags(version: Any) -> dict[str, str]:
    return {str(key): str(value) for key, value in (version.tags or {}).items()}


def _set_version_tags(client: Any, model_name: str, version: str, tags: Mapping[str, Any]) -> None:
    for key, value in tags.items():
        client.set_model_version_tag(model_name, version, key, str(value))


def _remove_alias_if_points_to(
    client: Any,
    model_name: str,
    alias: str,
    version: str,
) -> None:
    try:
        existing = client.get_model_version_by_alias(model_name, alias)
    except Exception:
        return
    if str(existing.version) == str(version):
        client.delete_registered_model_alias(model_name, alias)


def _source_run(client: Any, version: Any) -> Any:
    source_run_id = _version_tags(version).get("source_run_id")
    if not source_run_id:
        raise GovernanceError("registered model version has no source_run_id tag")
    try:
        return client.get_run(source_run_id)
    except Exception as exc:
        raise GovernanceError(
            f"source MLflow run does not exist: {source_run_id}"
        ) from exc


def governance_evidence(
    report: Mapping[str, Any],
    version: Any,
    source_run: Any,
    *,
    minimum_f1: float,
) -> dict[str, Any]:
    """Validate evidence without mutating MLflow state."""

    if not 0 <= minimum_f1 <= 1:
        raise GovernanceError("minimum_f1 must be between 0 and 1")

    evaluation = report.get("evaluation")
    if not isinstance(evaluation, Mapping):
        return {"passed": False, "reason": "missing evaluation section"}
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, Mapping) or "f1" not in metrics:
        return {"passed": False, "reason": "evaluation F1 metric is missing"}

    split = report.get("split")
    if split != "validation":
        return {
            "passed": False,
            "reason": "production governance requires a validation split report",
            "split": split,
        }

    try:
        observed_f1 = float(metrics["f1"])
    except (TypeError, ValueError):
        return {"passed": False, "reason": "evaluation F1 is not numeric"}

    version_tags = _version_tags(version)
    source_run_tags = {str(k): str(v) for k, v in source_run.data.tags.items()}
    training_run_id = report.get("training_run_id") or report.get("model", {}).get(
        "training_run_id"
    )
    source_run_id = version_tags.get("source_run_id")
    if training_run_id != source_run_id:
        return {
            "passed": False,
            "reason": "evaluation report does not identify the registered training run",
            "evaluation_training_run_id": training_run_id,
            "registered_source_run_id": source_run_id,
        }

    report_dataset = report.get("dataset", {})
    report_revision = report_dataset.get("dataset_revision")
    registered_revision = version_tags.get("dataset_revision") or source_run_tags.get(
        "dataset_revision"
    )
    if report_revision and registered_revision and report_revision != registered_revision:
        return {
            "passed": False,
            "reason": "evaluation dataset revision differs from registered model dataset",
            "evaluation_dataset_revision": report_revision,
            "registered_dataset_revision": registered_revision,
        }

    passed = observed_f1 >= minimum_f1
    return {
        "passed": passed,
        "reason": "validation F1 meets configured threshold" if passed else "validation F1 is below configured threshold",
        "metric": "f1",
        "observed_f1": observed_f1,
        "minimum_f1": minimum_f1,
        "split": split,
        "training_run_id": source_run_id,
        "dataset_revision": report_revision or registered_revision or "unknown",
    }


def validate_model_version(
    *,
    tracking_uri: str,
    model_name: str,
    version: str,
    evaluation_report: str | Path,
    minimum_f1: float,
) -> dict[str, Any]:
    """Move a candidate to validated or rejected based on immutable evidence."""

    mlflow, MlflowClient = _require_mlflow()
    mlflow.set_tracking_uri(tracking_uri)
    registry_uri = os.getenv("MLFLOW_REGISTRY_URI")
    if registry_uri:
        mlflow.set_registry_uri(registry_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    try:
        model_version = client.get_model_version(model_name, str(version))
    except Exception as exc:
        raise GovernanceError(f"model version does not exist: {model_name}/{version}") from exc
    if model_version.status != "READY":
        raise GovernanceError(
            f"model version is not READY: {model_name}/{version} ({model_version.status})"
        )

    report, report_hash = _read_report(evaluation_report)
    source_run = _source_run(client, model_version)
    decision = governance_evidence(
        report,
        model_version,
        source_run,
        minimum_f1=minimum_f1,
    )
    timestamp = _now()
    status = "validated" if decision["passed"] else "rejected"
    tags = {
        "lifecycle_status": status,
        "model_type": "transformer-sequence-classification",
        "validation_metric": "f1",
        "validation_f1": decision.get("observed_f1", "unknown"),
        "minimum_f1": minimum_f1,
        "validation_split": decision.get("split", "unknown"),
        "validation_reason": decision["reason"],
        "validation_timestamp": timestamp,
        "evaluation_report_sha256": report_hash,
        "evaluation_git_commit": report.get("git_commit", "unknown"),
        "dataset_revision": decision.get("dataset_revision", "unknown"),
        "git_commit": _version_tags(model_version).get("git_commit", "unknown"),
    }
    _set_version_tags(client, model_name, str(version), tags)
    if status == "validated":
        client.set_registered_model_alias(model_name, "validated", str(version))
        _remove_alias_if_points_to(client, model_name, "candidate", str(version))
    else:
        client.set_registered_model_alias(model_name, "rejected", str(version))
        _remove_alias_if_points_to(client, model_name, "candidate", str(version))

    return json_safe(
        {
            "model_name": model_name,
            "version": str(version),
            "lifecycle_status": status,
            "alias": status,
            "decision": decision,
            "validation_timestamp": timestamp,
            "evaluation_report_sha256": report_hash,
        }
    )


def promote_validated_version(
    *,
    tracking_uri: str,
    model_name: str,
    version: str,
) -> dict[str, Any]:
    """Assign the production alias only to a validated model version."""

    mlflow, MlflowClient = _require_mlflow()
    mlflow.set_tracking_uri(tracking_uri)
    registry_uri = os.getenv("MLFLOW_REGISTRY_URI")
    if registry_uri:
        mlflow.set_registry_uri(registry_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    model_version = client.get_model_version(model_name, str(version))
    tags = _version_tags(model_version)

    if tags.get("lifecycle_status") != "validated":
        raise GovernanceError(
            "production promotion requires lifecycle_status=validated; "
            f"received {tags.get('lifecycle_status', 'missing')}"
        )
    try:
        validated_alias = client.get_model_version_by_alias(model_name, "validated")
    except Exception as exc:
        raise GovernanceError("validated alias is missing") from exc
    if str(validated_alias.version) != str(version):
        raise GovernanceError("validated alias does not point to the requested version")

    previous_version = None
    try:
        previous = client.get_model_version_by_alias(model_name, "production")
        previous_version = str(previous.version)
    except Exception:
        pass

    timestamp = _now()
    promoted_by = os.getenv("GITHUB_ACTOR", os.getenv("USER", "unknown"))
    promotion_tags = {
        "lifecycle_status": "production",
        "promotion_timestamp": timestamp,
        "promoted_by": promoted_by,
        "production_previous_version": previous_version or "none",
        "model_type": tags.get("model_type", "transformer-sequence-classification"),
        "dataset_revision": tags.get("dataset_revision", "unknown"),
        "git_commit": tags.get("git_commit", "unknown"),
    }
    _set_version_tags(client, model_name, str(version), promotion_tags)
    client.set_registered_model_alias(model_name, "production", str(version))
    client.set_registered_model_tag(model_name, "production_version", str(version))

    return {
        "model_name": model_name,
        "version": str(version),
        "lifecycle_status": "production",
        "alias": "production",
        "previous_production_version": previous_version,
        "promotion_timestamp": timestamp,
        "promoted_by": promoted_by,
    }
