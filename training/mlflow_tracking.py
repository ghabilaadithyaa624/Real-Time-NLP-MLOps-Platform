"""MLflow tracking integration for completed local training runs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from training.config import ExperimentConfig
from training.utils import json_safe


def _require_mlflow() -> Any:
    try:
        import mlflow
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "MLflow is required for experiment tracking. Install the project "
            "dependencies before enabling MLflow."
        ) from exc
    return mlflow


def resolved_tracking_uri(config: ExperimentConfig) -> str:
    """Resolve environment override without putting secrets in YAML."""

    return os.getenv("MLFLOW_TRACKING_URI", config.mlflow.tracking_uri)


def _flatten_scalar_metrics(prefix: str, values: Mapping[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key, value in values.items():
        if isinstance(value, bool):
            continue
        try:
            metrics[f"{prefix}_{key}"] = float(value)
        except (TypeError, ValueError):
            continue
    return metrics


def _tracking_params(config: ExperimentConfig, summary: Mapping[str, Any]) -> dict[str, Any]:
    dataset = summary["dataset"]
    training = summary["training"]
    return {
        "model_name": config.model.name,
        "model_revision": config.model.revision or "local",
        "dataset_name": dataset["dataset_name"],
        "dataset_revision": dataset["dataset_revision"],
        "dataset_seed": config.dataset.seed,
        "validation_size": config.dataset.validation_size,
        "max_length": config.preprocessing.max_length,
        "batch_size": config.training.batch_size,
        "learning_rate": config.training.learning_rate,
        "epochs": config.training.epochs,
        "governance_metric": config.governance.metric,
        "governance_minimum_f1": config.governance.minimum_f1,
        "device": training["device"]["device"],
        "git_commit": summary["git_commit"],
    }


def log_training_run(
    config: ExperimentConfig,
    summary: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Log a completed run and its Hugging Face model to MLflow.

    This function does not register a model version or assign an alias. Model
    registration is an explicit follow-up command in ``register_model.py``.
    """

    mlflow = _require_mlflow()
    config.validate()
    output_path = Path(output_dir)
    if not output_path.exists():
        raise FileNotFoundError(f"training output does not exist: {output_path}")

    tracking_uri = resolved_tracking_uri(config)
    mlflow.set_tracking_uri(tracking_uri)
    registry_uri = os.getenv("MLFLOW_REGISTRY_URI")
    if registry_uri:
        mlflow.set_registry_uri(registry_uri)
    mlflow.set_experiment(config.mlflow.experiment_name)

    run_name = f"{config.mlflow.registered_model_name}-{summary['git_commit'][:8]}"
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(_tracking_params(config, summary))

        metric_values: dict[str, float] = {}
        metric_values.update(
            _flatten_scalar_metrics("train", summary["metrics"].get("train", {}))
        )
        metric_values.update(
            _flatten_scalar_metrics(
                "validation", summary["metrics"].get("validation", {})
            )
        )
        if metric_values:
            mlflow.log_metrics(metric_values)

        mlflow.set_tags(
            {
                "model_name": config.model.name,
                "model_revision": config.model.revision or "local",
                "dataset_name": summary["dataset"]["dataset_name"],
                "dataset_revision": summary["dataset"]["dataset_revision"],
                "git_commit": summary["git_commit"],
                "model_lifecycle_status": "candidate",
                "registry_alias": "none",
            }
        )
        mlflow.log_dict(json_safe(summary["dataset"]), "dataset_metadata.json")
        mlflow.log_dict(json_safe(config_to_dict(config)), "training_config.json")

        summary_path = output_path / "training_summary.json"
        if summary_path.exists():
            mlflow.log_artifact(str(summary_path), artifact_path="run")
        trainer_state = output_path / "trainer_state.json"
        if trainer_state.exists():
            mlflow.log_artifact(str(trainer_state), artifact_path="run")

        try:
            # MLflow 2.x accepts a local Hugging Face checkpoint directory and
            # packages the model plus tokenizer as one Transformers artifact.
            model_info = mlflow.transformers.log_model(
                transformers_model=str(output_path),
                artifact_path="model",
                task="text-classification",
                # Explicit requirements avoid MLflow probing optional
                # torchvision/TensorFlow integrations that serving does not use.
                pip_requirements=[
                    "mlflow==2.19.0",
                    "transformers==4.48.3",
                    "torch==2.5.1",
                    "tokenizers==0.21.4",
                    "safetensors==0.8.0",
                ],
            )
        except Exception as exc:
            raise RuntimeError(
                "MLflow model logging failed after the run metadata was created"
            ) from exc

        model_uri = getattr(model_info, "model_uri", f"runs:/{run.info.run_id}/model")
        return {
            "tracking_uri": tracking_uri,
            "experiment_name": config.mlflow.experiment_name,
            "run_id": run.info.run_id,
            "run_name": run_name,
            "model_uri": model_uri,
            "registered_model_name": config.mlflow.registered_model_name,
        }


def config_to_dict(config: ExperimentConfig) -> dict[str, Any]:
    """Serialize config sections without requiring a YAML re-read."""

    return {
        "dataset": {
            "name": config.dataset.name,
            "config": config.dataset.config,
            "revision": config.dataset.revision,
            "train_split": config.dataset.train_split,
            "test_split": config.dataset.test_split,
            "validation_size": config.dataset.validation_size,
            "seed": config.dataset.seed,
            "label_names": dict(config.dataset.label_names),
        },
        "model": {
            "name": config.model.name,
            "revision": config.model.revision,
        },
        "preprocessing": {
            "max_length": config.preprocessing.max_length,
            "padding": config.preprocessing.padding,
            "truncation": config.preprocessing.truncation,
        },
        "training": {
            "batch_size": config.training.batch_size,
            "learning_rate": config.training.learning_rate,
            "epochs": config.training.epochs,
            "warmup_ratio": config.training.warmup_ratio,
            "weight_decay": config.training.weight_decay,
        },
        "governance": {
            "metric": config.governance.metric,
            "minimum_f1": config.governance.minimum_f1,
        },
        "mlflow": {
            "tracking_uri": config.mlflow.tracking_uri,
            "experiment_name": config.mlflow.experiment_name,
            "registered_model_name": config.mlflow.registered_model_name,
        },
    }
