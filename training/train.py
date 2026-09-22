"""Fine-tune a configurable Hugging Face sequence classifier.

MLflow logging is optional for local runs and model registration remains a
separate explicit command. The script always creates a local, provenance-rich
training summary and can additionally log the run to MLflow.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from app.inference.preprocessing import tokenize_dataset
from app.inference.tokenizer import load_tokenizer
from training.config import ExperimentConfig, load_experiment_config
from training.dataset import build_dataset, dataset_metadata
from training.metrics import compute_metrics
from training.utils import device_summary, git_commit, seed_everything, write_json


def _require_training_dependencies() -> tuple[Any, Any, Any, Any]:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Training requires torch, transformers, and accelerate. Install the "
            "project dependencies before running training."
        ) from exc
    return torch, AutoModelForSequenceClassification, Trainer, TrainingArguments


def _load_model(config: ExperimentConfig, model_num_labels: int, model_labels: dict[int, str]) -> Any:
    _, auto_model, _, _ = _require_training_dependencies()
    model_kwargs: dict[str, Any] = {
        "num_labels": model_num_labels,
        "id2label": model_labels,
        "label2id": {label: index for index, label in model_labels.items()},
    }

    # Local smoke-test models do not need a Hub revision. Remote models must
    # use the pinned revision from config.
    if config.model.revision and not Path(config.model.name).exists():
        model_kwargs["revision"] = config.model.revision

    return auto_model.from_pretrained(config.model.name, **model_kwargs)


def _training_arguments(config: ExperimentConfig, output_dir: Path) -> Any:
    _, _, _, training_arguments = _require_training_dependencies()
    compute_device = device_summary()
    use_cuda = bool(compute_device["cuda_available"])

    return training_arguments(
        output_dir=str(output_dir),
        overwrite_output_dir=True,
        per_device_train_batch_size=config.training.batch_size,
        per_device_eval_batch_size=config.training.batch_size,
        learning_rate=config.training.learning_rate,
        num_train_epochs=config.training.epochs,
        weight_decay=config.training.weight_decay,
        warmup_ratio=config.training.warmup_ratio,
        logging_strategy="steps",
        logging_steps=config.training.logging_steps,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=config.training.save_total_limit,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        seed=config.dataset.seed,
        data_seed=config.dataset.seed,
        use_cpu=not use_cuda,
        fp16=bool(config.training.fp16 and use_cuda),
        report_to=[],
        remove_unused_columns=True,
        save_safetensors=True,
    )


def _select_limit(dataset: Any, limit: int | None) -> Any:
    if limit is None:
        return dataset
    if limit <= 0:
        raise ValueError("sample limits must be positive")
    return dataset.select(range(min(limit, dataset.num_rows)))


def run_training(
    config: ExperimentConfig,
    *,
    output_dir: str | Path | None = None,
    max_train_samples: int | None = None,
    max_eval_samples: int | None = None,
    enable_mlflow: bool | None = None,
) -> dict[str, Any]:
    """Run fine-tuning and return a serializable training summary."""

    torch, _, trainer_class, _ = _require_training_dependencies()
    config.validate()
    seed_everything(config.dataset.seed)

    output_path = Path(output_dir or config.training.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    raw_dataset = build_dataset(config.dataset)
    raw_metadata = dataset_metadata(raw_dataset, config.dataset)

    tokenizer = load_tokenizer(
        config.model.name,
        revision=config.model.revision,
        cache_dir=config.dataset.cache_dir,
    )
    tokenized_dataset = tokenize_dataset(
        raw_dataset,
        tokenizer,
        config.preprocessing,
    )
    tokenized_dataset["train"] = _select_limit(
        tokenized_dataset["train"], max_train_samples
    )
    tokenized_dataset["validation"] = _select_limit(
        tokenized_dataset["validation"], max_eval_samples
    )

    label_names = dict(config.dataset.label_names)
    model = _load_model(config, len(label_names), label_names)
    model.config.problem_type = "single_label_classification"
    training_args = _training_arguments(config, output_path)

    trainer = trainer_class(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["validation"],
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
    )

    train_result = trainer.train()
    evaluation_metrics = trainer.evaluate()
    trainer.save_model(str(output_path))
    tokenizer.save_pretrained(str(output_path))
    trainer.save_state()

    summary = {
        "git_commit": git_commit(),
        "model": {
            "name": config.model.name,
            "revision": config.model.revision,
            "num_labels": len(label_names),
            "labels": {str(index): name for index, name in label_names.items()},
        },
        "dataset": raw_metadata,
        "preprocessing": {
            "max_length": config.preprocessing.max_length,
            "padding": config.preprocessing.padding,
            "truncation": config.preprocessing.truncation,
        },
        "training": {
            "batch_size": config.training.batch_size,
            "learning_rate": config.training.learning_rate,
            "epochs": config.training.epochs,
            "seed": config.dataset.seed,
            "best_checkpoint": trainer.state.best_model_checkpoint,
            "best_metric": trainer.state.best_metric,
            "device": device_summary(),
            "torch_version": torch.__version__,
            "train_samples_used": tokenized_dataset["train"].num_rows,
            "validation_samples_used": tokenized_dataset["validation"].num_rows,
        },
        "metrics": {
            "train": train_result.metrics,
            "validation": evaluation_metrics,
            # Trainer log history contains per-step loss/learning-rate entries
            # as well as per-epoch validation metrics.
            "history": trainer.state.log_history,
        },
    }
    write_json(output_path / "training_summary.json", summary)

    mlflow_enabled = config.mlflow.enabled if enable_mlflow is None else enable_mlflow
    if mlflow_enabled:
        from training.mlflow_tracking import log_training_run

        summary["mlflow"] = log_training_run(config, summary, output_path)
        # The first summary is logged as a run artifact; this second write keeps
        # the local summary linked to the resulting MLflow run as well.
        write_json(output_path / "training_summary.json", summary)

    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="training/config.yaml")
    parser.add_argument("--output-dir")
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-eval-samples", type=int)
    parser.add_argument(
        "--with-mlflow",
        action="store_true",
        help="enable MLflow tracking for this run",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_experiment_config(args.config)
    summary = run_training(
        config,
        output_dir=args.output_dir,
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
        enable_mlflow=True if args.with_mlflow else None,
    )
    print(summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
