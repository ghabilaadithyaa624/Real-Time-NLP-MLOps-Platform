"""Evaluate a saved Transformer checkpoint on validation or test data.

Evaluation is read-only with respect to model promotion. It writes reports and
an explicit threshold result; it does not register or promote a model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

from app.inference.preprocessing import tokenize_dataset
from app.inference.tokenizer import load_tokenizer
from training.config import ExperimentConfig, load_experiment_config
from training.dataset import build_dataset, dataset_metadata
from training.metrics import classification_metrics
from training.train import _require_training_dependencies
from training.utils import device_summary, git_commit, json_safe, write_json


def evaluate_predictions(
    predictions: Any,
    labels: Any,
    label_names: Mapping[int, str],
    *,
    minimum_f1: float,
) -> dict[str, Any]:
    """Create metrics, confusion matrix, report, and a non-promoting gate result."""

    if not 0 <= minimum_f1 <= 1:
        raise ValueError("minimum_f1 must be between 0 and 1")

    prediction_array = np.asarray(predictions)
    if prediction_array.ndim > 1:
        prediction_array = prediction_array.argmax(axis=-1)
    prediction_array = prediction_array.reshape(-1)
    label_array = np.asarray(labels).reshape(-1)

    if len(prediction_array) != len(label_array):
        raise ValueError("predictions and labels must have the same number of items")

    ordered_labels = sorted(label_names)
    names = [label_names[index] for index in ordered_labels]
    metrics = classification_metrics(prediction_array, label_array)
    matrix = confusion_matrix(
        label_array,
        prediction_array,
        labels=ordered_labels,
    )
    report = classification_report(
        label_array,
        prediction_array,
        labels=ordered_labels,
        target_names=names,
        output_dict=True,
        zero_division=0,
    )

    return {
        "num_examples": int(len(label_array)),
        "label_names": {str(index): name for index, name in label_names.items()},
        "metrics": metrics,
        "confusion_matrix": matrix.tolist(),
        "classification_report": report,
        "governance_check": {
            "metric": "f1",
            "minimum_f1": minimum_f1,
            "observed_f1": metrics["f1"],
            "passed": bool(metrics["f1"] >= minimum_f1),
        },
    }


def _evaluation_arguments(config: ExperimentConfig, output_dir: Path) -> Any:
    _, _, _, training_arguments = _require_training_dependencies()
    use_cuda = bool(device_summary()["cuda_available"])
    return training_arguments(
        output_dir=str(output_dir),
        per_device_eval_batch_size=config.training.batch_size,
        do_train=False,
        do_eval=True,
        report_to=[],
        use_cpu=not use_cuda,
        fp16=False,
        remove_unused_columns=True,
    )


def evaluate_checkpoint(
    config: ExperimentConfig,
    model_path: str | Path,
    *,
    split: str = "test",
    output_dir: str | Path = "artifacts/evaluation",
    minimum_f1: float | None = None,
    max_samples: int | None = None,
) -> dict[str, Any]:
    """Evaluate a local checkpoint and write JSON/CSV-friendly artifacts."""

    torch, auto_model, trainer_class, _ = _require_training_dependencies()
    config.validate()
    if split not in {"validation", "test"}:
        raise ValueError("split must be 'validation' or 'test'")
    if max_samples is not None and max_samples <= 0:
        raise ValueError("max_samples must be positive")

    checkpoint_path = Path(model_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"model checkpoint does not exist: {checkpoint_path}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    threshold = (
        config.governance.minimum_f1 if minimum_f1 is None else minimum_f1
    )
    if not 0 <= threshold <= 1:
        raise ValueError("minimum_f1 must be between 0 and 1")

    raw_dataset = build_dataset(config.dataset)
    tokenized_dataset = tokenize_dataset(
        raw_dataset,
        load_tokenizer(str(checkpoint_path), local_files_only=True),
        config.preprocessing,
    )
    evaluation_dataset = tokenized_dataset[split]
    if max_samples is not None:
        evaluation_dataset = evaluation_dataset.select(
            range(min(max_samples, evaluation_dataset.num_rows))
        )

    model = auto_model.from_pretrained(str(checkpoint_path))
    trainer = trainer_class(
        model=model,
        args=_evaluation_arguments(config, output_path),
        processing_class=load_tokenizer(
            str(checkpoint_path), local_files_only=True
        ),
    )
    prediction_output = trainer.predict(evaluation_dataset, metric_key_prefix=split)
    report = evaluate_predictions(
        prediction_output.predictions,
        prediction_output.label_ids,
        config.dataset.label_names,
        minimum_f1=threshold,
    )

    training_run_id = None
    training_summary_path = checkpoint_path / "training_summary.json"
    if training_summary_path.exists():
        try:
            training_summary = json.loads(
                training_summary_path.read_text(encoding="utf-8")
            )
            training_run_id = training_summary.get("mlflow", {}).get("run_id")
        except (OSError, json.JSONDecodeError, AttributeError):
            training_run_id = None

    result = {
        "git_commit": git_commit(),
        "training_run_id": training_run_id,
        "model": {
            "checkpoint": str(checkpoint_path),
            "configured_name": config.model.name,
            "configured_revision": config.model.revision,
            "training_run_id": training_run_id,
            "torch_version": torch.__version__,
            "device": device_summary(),
        },
        "dataset": dataset_metadata(raw_dataset, config.dataset),
        "split": split,
        "minimum_f1": threshold,
        "evaluation": report,
    }
    write_json(output_path / "evaluation_report.json", result)
    write_json(output_path / "confusion_matrix.json", report["confusion_matrix"])
    write_json(
        output_path / "classification_report.json",
        report["classification_report"],
    )
    return json_safe(result)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="training/config.yaml")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--output-dir", default="artifacts/evaluation")
    parser.add_argument("--minimum-f1", type=float)
    parser.add_argument("--max-samples", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_experiment_config(args.config)
    result = evaluate_checkpoint(
        config,
        args.model_path,
        split=args.split,
        output_dir=args.output_dir,
        minimum_f1=args.minimum_f1,
        max_samples=args.max_samples,
    )
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
