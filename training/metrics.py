"""Classification metrics used during Transformer training and evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support


def classification_metrics(predictions: Any, labels: Any) -> dict[str, float]:
    """Calculate metrics with macro averaging for binary/multiclass support."""

    predictions_array = np.asarray(predictions)
    labels_array = np.asarray(labels)

    if predictions_array.ndim > 1:
        predictions_array = predictions_array.argmax(axis=-1)
    predictions_array = predictions_array.reshape(-1)
    labels_array = labels_array.reshape(-1)

    if len(predictions_array) != len(labels_array):
        raise ValueError("predictions and labels must have the same number of items")

    precision, recall, f1, _ = precision_recall_fscore_support(
        labels_array,
        predictions_array,
        average="macro",
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(labels_array, predictions_array)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def compute_metrics(eval_prediction: Any) -> dict[str, float]:
    """Adapter for Hugging Face Trainer's EvalPrediction object."""

    predictions = eval_prediction.predictions
    if isinstance(predictions, tuple):
        predictions = predictions[0]
    return classification_metrics(predictions, eval_prediction.label_ids)
