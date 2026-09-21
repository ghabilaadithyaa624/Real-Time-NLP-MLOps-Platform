from types import SimpleNamespace

import pytest
import torch

from app.inference.predictor import (
    PredictionResult,
    PredictorNotReady,
    TransformerPredictor,
)
from app.inference.preprocessing import PreprocessingConfig
from app.inference.settings import InferenceSettings


class RecordingTokenizer:
    def __call__(self, texts, **kwargs):
        max_length = kwargs["max_length"]
        return {
            "input_ids": [[1] * max_length for _ in texts],
            "attention_mask": [[1] * max_length for _ in texts],
        }


class RecordingModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.config = SimpleNamespace(id2label={0: "negative", 1: "positive"})
        self.grad_enabled_during_forward = None
        self.forward_calls = 0

    def forward(self, input_ids, attention_mask):
        self.forward_calls += 1
        self.grad_enabled_during_forward = torch.is_grad_enabled()
        return SimpleNamespace(logits=torch.tensor([[1.0, 3.0]]))


def test_predictor_keeps_model_in_memory_and_uses_inference_mode():
    model = RecordingModel()
    predictor = TransformerPredictor(
        model=model,
        tokenizer=RecordingTokenizer(),
        preprocessing=PreprocessingConfig(max_length=4),
        model_version="production",
        device="cpu",
    )

    first = predictor.predict("good feedback")
    second = predictor.predict("another feedback")

    assert isinstance(first, PredictionResult)
    assert first.prediction == "positive"
    assert first.confidence > 0.5
    assert second.model_version == "production"
    assert model.forward_calls == 2
    assert model.grad_enabled_during_forward is False


def test_model_rejects_sequence_length_beyond_architecture_limit():
    model = RecordingModel()
    model.config.max_position_embeddings = 4

    with pytest.raises(PredictorNotReady, match="max_position_embeddings"):
        TransformerPredictor(
            model=model,
            tokenizer=RecordingTokenizer(),
            preprocessing=PreprocessingConfig(max_length=8),
            model_version="production",
            device="cpu",
        )


def test_inference_settings_default_to_production_mlflow(monkeypatch):
    for name in (
        "MODEL_SOURCE",
        "MODEL_PATH",
        "MLFLOW_MODEL_URI",
        "MODEL_VERSION",
        "MODEL_LABELS",
        "INFERENCE_DEVICE",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = InferenceSettings.from_environment()

    assert settings.model_source == "mlflow"
    assert settings.mlflow_model_uri.endswith("@production")
    assert settings.model_version == "production"
    assert settings.max_length == 128


def test_local_mode_requires_model_path(monkeypatch):
    monkeypatch.setenv("MODEL_SOURCE", "local")
    monkeypatch.delenv("MODEL_PATH", raising=False)

    with pytest.raises(ValueError, match="MODEL_PATH"):
        InferenceSettings.from_environment()
