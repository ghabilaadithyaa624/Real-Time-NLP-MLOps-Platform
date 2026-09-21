"""In-memory Transformer predictor for local and MLflow model sources."""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import torch

from app.inference.preprocessing import PreprocessingConfig, tokenize_batch
from app.inference.tokenizer import load_tokenizer


@dataclass(frozen=True)
class PredictionResult:
    """Stable prediction payload returned by the inference layer."""

    prediction: str
    confidence: float
    model_version: str


class PredictorNotReady(RuntimeError):
    """Raised when a model cannot be loaded or is not initialized."""


class TransformerPredictor:
    """Keep a tokenizer and sequence-classification model in memory."""

    def __init__(
        self,
        *,
        model: Any,
        tokenizer: Any,
        preprocessing: PreprocessingConfig,
        model_version: str,
        label_names: Mapping[int, str] | None = None,
        device: str | None = None,
        model_source: str = "local",
    ) -> None:
        preprocessing.validate()
        self.model = model
        self.tokenizer = tokenizer
        self.preprocessing = preprocessing
        self.model_version = model_version
        self.model_source = model_source
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model.to(self.device)
        self.model.eval()

        configured_labels = dict(label_names or {})
        model_labels = getattr(getattr(model, "config", None), "id2label", {}) or {}
        normalized_model_labels = {
            int(index): str(label) for index, label in model_labels.items()
        }
        self.label_names = configured_labels or normalized_model_labels
        if not self.label_names:
            raise ValueError("model must provide an id2label mapping")

    @classmethod
    def from_local(
        cls,
        model_path: str | Path,
        *,
        preprocessing: PreprocessingConfig,
        model_version: str = "local",
        label_names: Mapping[int, str] | None = None,
        model_revision: str | None = None,
    ) -> "TransformerPredictor":
        try:
            from transformers import AutoModelForSequenceClassification
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise PredictorNotReady("transformers is required for model loading") from exc

        path = Path(model_path)
        if not path.exists():
            raise PredictorNotReady(f"local model path does not exist: {path}")
        tokenizer = load_tokenizer(str(path), local_files_only=True)
        kwargs: dict[str, Any] = {}
        if model_revision:
            kwargs["revision"] = model_revision
        model = AutoModelForSequenceClassification.from_pretrained(str(path), **kwargs)
        return cls(
            model=model,
            tokenizer=tokenizer,
            preprocessing=preprocessing,
            model_version=model_version,
            label_names=label_names,
            model_source="local",
        )

    @classmethod
    def from_mlflow(
        cls,
        model_uri: str,
        *,
        preprocessing: PreprocessingConfig,
        model_version: str = "production",
        label_names: Mapping[int, str] | None = None,
    ) -> "TransformerPredictor":
        if not model_uri.strip():
            raise PredictorNotReady("MLflow model URI must not be empty")
        try:
            import mlflow
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise PredictorNotReady("mlflow is required for MLflow model loading") from exc

        try:
            pipeline = mlflow.transformers.load_model(model_uri)
            model = pipeline.model
            tokenizer = pipeline.tokenizer
        except Exception as exc:
            raise PredictorNotReady(
                f"could not load MLflow model: {model_uri}"
            ) from exc
        return cls(
            model=model,
            tokenizer=tokenizer,
            preprocessing=preprocessing,
            model_version=model_version,
            label_names=label_names,
            model_source="mlflow",
        )

    @classmethod
    def from_environment(
        cls,
        *,
        preprocessing: PreprocessingConfig | None = None,
        label_names: Mapping[int, str] | None = None,
    ) -> "TransformerPredictor":
        """Load the configured model; MLflow is the production default."""

        source = os.getenv("MODEL_SOURCE", "mlflow").strip().lower()
        model_version = os.getenv("MODEL_VERSION", "production")
        preprocessing = preprocessing or PreprocessingConfig(
            max_length=int(os.getenv("MAX_LENGTH", "128"))
        )
        label_names = label_names or _labels_from_environment()

        if source == "local":
            model_path = os.getenv("MODEL_PATH", "")
            return cls.from_local(
                model_path,
                preprocessing=preprocessing,
                model_version=model_version,
                label_names=label_names,
                model_revision=os.getenv("MODEL_REVISION"),
            )
        if source == "mlflow":
            model_uri = os.getenv(
                "MLFLOW_MODEL_URI",
                "models:/customer-feedback-classifier@production",
            )
            return cls.from_mlflow(
                model_uri,
                preprocessing=preprocessing,
                model_version=model_version,
                label_names=label_names,
            )
        raise PredictorNotReady(f"unsupported MODEL_SOURCE: {source}")

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def predict(self, text: str) -> PredictionResult:
        if not self.is_ready:
            raise PredictorNotReady("predictor is not initialized")

        encoded = tokenize_batch(self.tokenizer, [text], self.preprocessing)
        model_inputs: dict[str, torch.Tensor] = {}
        try:
            model_input_names = set(inspect.signature(self.model.forward).parameters)
        except (TypeError, ValueError):
            model_input_names = {"input_ids", "attention_mask"}
        for field_name, values in encoded.items():
            if field_name in {"input_ids", "attention_mask", "token_type_ids"}:
                if not model_input_names or field_name in model_input_names:
                    model_inputs[field_name] = torch.tensor(values, device=self.device)

        with torch.inference_mode():
            outputs = self.model(**model_inputs)
            probabilities = torch.softmax(outputs.logits, dim=-1)[0]

        class_index = int(torch.argmax(probabilities).item())
        label = self.label_names.get(class_index, str(class_index))
        return PredictionResult(
            prediction=label,
            confidence=float(probabilities[class_index].item()),
            model_version=self.model_version,
        )


def _labels_from_environment() -> dict[int, str] | None:
    raw = os.getenv("MODEL_LABELS")
    if not raw:
        return None
    try:
        values = json.loads(raw)
        return {int(index): str(label) for index, label in values.items()}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PredictorNotReady("MODEL_LABELS must be a JSON object") from exc
