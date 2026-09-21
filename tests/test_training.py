from types import SimpleNamespace

import numpy as np
import pytest

from training.config import load_experiment_config
from training.metrics import classification_metrics, compute_metrics
from training.utils import device_summary, git_commit, seed_everything


def test_experiment_config_loads_all_phase_four_settings():
    config = load_experiment_config("training/config.yaml")

    assert config.model.name == "distilbert-base-uncased"
    assert config.preprocessing.max_length == 128
    assert config.training.batch_size == 16
    assert config.training.learning_rate == 2.0e-5
    assert config.training.epochs == 3


def test_classification_metrics_support_logits_and_macro_scores():
    metrics = classification_metrics(
        np.array([[4.0, 1.0], [0.5, 2.0], [3.0, 1.0], [0.2, 1.5]]),
        np.array([0, 1, 1, 1]),
    )

    assert metrics == {
        "accuracy": 0.75,
        "precision": pytest.approx(0.75),
        "recall": pytest.approx(0.8333333333),
        "f1": pytest.approx(0.7333333333),
    }


def test_compute_metrics_accepts_trainer_prediction():
    result = compute_metrics(
        SimpleNamespace(
            predictions=np.array([[2.0, 0.0], [0.0, 2.0]]),
            label_ids=np.array([0, 1]),
        )
    )
    assert result == {"accuracy": 1.0, "precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_seed_and_provenance_helpers_are_available():
    seed_everything(42)
    assert device_summary()["device"] in {"cpu", "cuda", "unavailable"}
    assert len(git_commit()) > 0
