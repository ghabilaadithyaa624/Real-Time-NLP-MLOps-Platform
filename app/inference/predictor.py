"""In-memory Transformer predictor for local and MLflow model sources."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import torch

from app.inference.preprocessing import PreprocessingConfig, tokenize_batch
from app.inference.settings import InferenceSettings
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
        warmup_text: str = "health check",
    ) -> None:
        preprocessing.validate()
        max_positions = getattr(
            getattr(model, "config", None), "max_position_embeddings", None
        )
        if max_positions is not None and preprocessing.max_length > int(max_positions):
            raise PredictorNotReady(
                "MAX_LENGTH exceeds the model max_position_embeddings: "
                f"{preprocessing.max_length} > {max_positions}"
            )
        self.model = model
        self.tokenizer = tokenizer
        self.preprocessing = preprocessing
        self.model_version = model_version
        self.model_source = model_source
        self.warmup_text = warmup_text
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
        device: str | None = None,
        warmup_text: str = "health check",
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
            device=device,
            model_source="local",
            warmup_text=warmup_text,
        )

    @classmethod
    def from_mlflow(
        cls,
        model_uri: str,
        *,
        preprocessing: PreprocessingConfig,
        model_version: str = "production",
        label_names: Mapping[int, str] | None = None,
        device: str | None = None,
        warmup_text: str = "health check",
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
            device=device,
            model_source="mlflow",
            warmup_text=warmup_text,
        )

    @classmethod
    def from_environment(
        cls,
        *,
        preprocessing: PreprocessingConfig | None = None,
        label_names: Mapping[int, str] | None = None,
    ) -> "TransformerPredictor":
        """Load the configured model; MLflow is the production default."""

        try:
            settings = InferenceSettings.from_environment()
        except (TypeError, ValueError) as exc:
            raise PredictorNotReady(str(exc)) from exc

        preprocessing = preprocessing or PreprocessingConfig(
            max_length=settings.max_length
        )
        label_names = label_names or settings.label_names
        device = None if settings.device == "auto" else settings.device

        if settings.device == "cuda" and not torch.cuda.is_available():
            raise PredictorNotReady("INFERENCE_DEVICE=cuda but CUDA is unavailable")

        if settings.model_source == "local":
            return cls.from_local(
                settings.model_path or "",
                preprocessing=preprocessing,
                model_version=settings.model_version,
                label_names=label_names,
                model_revision=settings.model_revision,
                device=device,
                warmup_text=settings.warmup_text,
            )
        return cls.from_mlflow(
            settings.mlflow_model_uri,
            preprocessing=preprocessing,
            model_version=settings.model_version,
            label_names=label_names,
            device=device,
            warmup_text=settings.warmup_text,
        )

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def warmup(self) -> None:
        """Run one safe synthetic inference before declaring readiness."""

        self.predict(self.warmup_text)

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
