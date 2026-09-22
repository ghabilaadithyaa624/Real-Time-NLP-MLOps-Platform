"""Environment-backed inference settings with explicit validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class InferenceSettings:
    model_source: str = "mlflow"
    model_path: str | None = None
    mlflow_model_uri: str = "models:/customer-feedback-classifier@production"
    model_version: str = "production"
    max_length: int = 128
    model_revision: str | None = None
    label_names: Mapping[int, str] | None = None
    device: str = "auto"
    warmup_text: str = "health check"

    def validate(self) -> None:
        if self.model_source not in {"local", "mlflow"}:
            raise ValueError("MODEL_SOURCE must be 'local' or 'mlflow'")
        if self.model_source == "local" and not self.model_path:
            raise ValueError("MODEL_PATH is required when MODEL_SOURCE=local")
        if self.model_source == "mlflow" and not self.mlflow_model_uri.strip():
            raise ValueError("MLFLOW_MODEL_URI must not be empty")
        if self.max_length <= 0:
            raise ValueError("MAX_LENGTH must be greater than zero")
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("INFERENCE_DEVICE must be auto, cpu, or cuda")
        if not self.warmup_text.strip():
            raise ValueError("MODEL_WARMUP_TEXT must not be empty")

    @classmethod
    def from_environment(cls) -> "InferenceSettings":
        raw_labels = os.getenv("MODEL_LABELS")
        label_names = None
        if raw_labels:
            try:
                values = json.loads(raw_labels)
                if not isinstance(values, dict):
                    raise ValueError("MODEL_LABELS must be a JSON object")
                label_names = {int(index): str(label) for index, label in values.items()}
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("MODEL_LABELS must be a JSON object") from exc

        settings = cls(
            model_source=os.getenv("MODEL_SOURCE", "mlflow").strip().lower(),
            model_path=os.getenv("MODEL_PATH") or None,
            mlflow_model_uri=os.getenv(
                "MLFLOW_MODEL_URI",
                "models:/customer-feedback-classifier@production",
            ),
            model_version=os.getenv("MODEL_VERSION", "production"),
            max_length=int(os.getenv("MAX_LENGTH", "128")),
            model_revision=os.getenv("MODEL_REVISION") or None,
            label_names=label_names,
            device=os.getenv("INFERENCE_DEVICE", "auto").strip().lower(),
            warmup_text=os.getenv("MODEL_WARMUP_TEXT", "health check"),
        )
        settings.validate()
        return settings
