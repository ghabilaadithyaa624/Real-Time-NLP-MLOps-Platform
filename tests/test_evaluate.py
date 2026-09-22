import numpy as np
import pytest

from training.evaluate import evaluate_predictions


def test_evaluation_generates_metrics_matrix_and_report():
    result = evaluate_predictions(
        np.array([[5.0, 1.0], [1.0, 5.0], [5.0, 1.0], [1.0, 5.0]]),
        np.array([0, 1, 1, 0]),
        {0: "negative", 1: "positive"},
        minimum_f1=0.90,
    )

    assert result["num_examples"] == 4
    assert result["metrics"] == {
        "accuracy": 0.5,
        "precision": pytest.approx(0.5),
        "recall": pytest.approx(0.5),
        "f1": pytest.approx(0.5),
    }
    assert result["confusion_matrix"] == [[1, 1], [1, 1]]
    assert result["classification_report"]["negative"]["f1-score"] == 0.5
    assert result["governance_check"]["passed"] is False


def test_evaluation_accepts_predictions_already_as_class_ids():
    result = evaluate_predictions(
        np.array([0, 1, 1, 0]),
        np.array([0, 1, 1, 0]),
        {0: "negative", 1: "positive"},
        minimum_f1=0.90,
    )

    assert result["metrics"]["f1"] == 1.0
    assert result["governance_check"]["passed"] is True


def test_invalid_threshold_is_rejected():
    with pytest.raises(ValueError, match="between 0 and 1"):
        evaluate_predictions(
            np.array([0]),
            np.array([0]),
            {0: "negative", 1: "positive"},
            minimum_f1=1.1,
        )
