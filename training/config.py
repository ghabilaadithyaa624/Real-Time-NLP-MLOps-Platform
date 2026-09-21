"""Typed access to the shared YAML experiment configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.inference.preprocessing import PreprocessingConfig
from training.dataset import DatasetConfig


@dataclass(frozen=True)
class ModelSettings:
    name: str = "distilbert-base-uncased"
    revision: str | None = None

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("model.name must not be empty")
        if self.revision is not None and not self.revision.strip():
            raise ValueError("model.revision must be non-empty when provided")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "ModelSettings":
        revision = values.get("revision")
        settings = cls(
            name=str(values.get("name", cls.name)),
            revision=None if revision in (None, "") else str(revision),
        )
        settings.validate()
        return settings


@dataclass(frozen=True)
class TrainingSettings:
    batch_size: int = 16
    learning_rate: float = 2.0e-5
    epochs: int = 3
    output_dir: str = "artifacts/training"
    logging_steps: int = 25
    save_total_limit: int = 2
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    fp16: bool = False

    def validate(self) -> None:
        if isinstance(self.batch_size, bool) or self.batch_size <= 0:
            raise ValueError("training.batch_size must be positive")
        if self.learning_rate <= 0:
            raise ValueError("training.learning_rate must be positive")
        if self.epochs <= 0:
            raise ValueError("training.epochs must be positive")
        if not self.output_dir.strip():
            raise ValueError("training.output_dir must not be empty")
        if self.logging_steps <= 0:
            raise ValueError("training.logging_steps must be positive")
        if self.save_total_limit <= 0:
            raise ValueError("training.save_total_limit must be positive")
        if not 0 <= self.warmup_ratio < 1:
            raise ValueError("training.warmup_ratio must be in [0, 1)")
        if self.weight_decay < 0:
            raise ValueError("training.weight_decay must not be negative")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "TrainingSettings":
        settings = cls(
            batch_size=int(values.get("batch_size", 16)),
            learning_rate=float(values.get("learning_rate", 2.0e-5)),
            epochs=int(values.get("epochs", 3)),
            output_dir=str(values.get("output_dir", "artifacts/training")),
            logging_steps=int(values.get("logging_steps", 25)),
            save_total_limit=int(values.get("save_total_limit", 2)),
            warmup_ratio=float(values.get("warmup_ratio", 0.1)),
            weight_decay=float(values.get("weight_decay", 0.01)),
            fp16=bool(values.get("fp16", False)),
        )
        settings.validate()
        return settings


@dataclass(frozen=True)
class GovernanceSettings:
    metric: str = "f1"
    minimum_f1: float = 0.90

    def validate(self) -> None:
        if self.metric != "f1":
            raise ValueError("only f1 is supported as the current governance metric")
        if not 0 <= self.minimum_f1 <= 1:
            raise ValueError("governance.minimum_f1 must be between 0 and 1")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "GovernanceSettings":
        settings = cls(
            metric=str(values.get("metric", "f1")),
            minimum_f1=float(values.get("minimum_f1", 0.90)),
        )
        settings.validate()
        return settings


@dataclass(frozen=True)
class MLflowSettings:
    enabled: bool = False
    tracking_uri: str = "file:./mlruns"
    experiment_name: str = "customer-feedback-classifier"
    registered_model_name: str = "customer-feedback-classifier"

    def validate(self) -> None:
        if not self.tracking_uri.strip():
            raise ValueError("mlflow.tracking_uri must not be empty")
        if not self.experiment_name.strip():
            raise ValueError("mlflow.experiment_name must not be empty")
        if not self.registered_model_name.strip():
            raise ValueError("mlflow.registered_model_name must not be empty")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "MLflowSettings":
        settings = cls(
            enabled=bool(values.get("enabled", False)),
            tracking_uri=str(values.get("tracking_uri", "file:./mlruns")),
            experiment_name=str(
                values.get("experiment_name", "customer-feedback-classifier")
            ),
            registered_model_name=str(
                values.get("registered_model_name", "customer-feedback-classifier")
            ),
        )
        settings.validate()
        return settings


@dataclass(frozen=True)
class ExperimentConfig:
    dataset: DatasetConfig
    preprocessing: PreprocessingConfig
    model: ModelSettings
    training: TrainingSettings
    governance: GovernanceSettings
    mlflow: MLflowSettings = field(default_factory=MLflowSettings)

    def validate(self) -> None:
        self.dataset.validate()
        self.preprocessing.validate()
        self.model.validate()
        self.training.validate()
        self.governance.validate()
        self.mlflow.validate()


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    """Load and validate all sections of a training YAML configuration."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("PyYAML is required to read training configuration") from exc

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}

    if not isinstance(document, Mapping):
        raise ValueError("configuration root must be a mapping")

    def section(name: str) -> Mapping[str, Any]:
        value = document.get(name, {})
        if not isinstance(value, Mapping):
            raise ValueError(f"configuration section {name!r} must be a mapping")
        return value

    config = ExperimentConfig(
        dataset=DatasetConfig.from_mapping(section("dataset")),
        preprocessing=PreprocessingConfig.from_mapping(section("preprocessing")),
        model=ModelSettings.from_mapping(section("model")),
        training=TrainingSettings.from_mapping(section("training")),
        governance=GovernanceSettings.from_mapping(section("governance")),
        mlflow=MLflowSettings.from_mapping(section("mlflow")),
    )
    config.validate()
    return config
