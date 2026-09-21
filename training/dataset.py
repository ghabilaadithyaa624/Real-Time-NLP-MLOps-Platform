"""Reproducible IMDb dataset loading and split metadata.

The module deliberately keeps the Hugging Face import inside ``load_dataset``.
This allows configuration and validation checks to run without downloading data,
and gives callers a clear dependency error when the data extra is not installed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_DATASET_NAME = "stanfordnlp/imdb"
DEFAULT_DATASET_CONFIG = "plain_text"
DEFAULT_DATASET_REVISION = "e6281661ce1c48d982bc483cf8a173c1bbeb5d31"
DEFAULT_SOURCE_URL = "https://ai.stanford.edu/~amaas/data/sentiment/"
DEFAULT_DATASET_CARD_URL = "https://huggingface.co/datasets/stanfordnlp/imdb"
DEFAULT_CITATION_URL = "https://aclanthology.org/P11-1015/"


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration required to build the supervised dataset.

    ``label_names`` is a mapping rather than a hard-coded binary conditional so
    the same pipeline can support a future multiclass dataset.
    """

    name: str = DEFAULT_DATASET_NAME
    config: str = DEFAULT_DATASET_CONFIG
    revision: str = DEFAULT_DATASET_REVISION
    train_split: str = "train"
    test_split: str = "test"
    validation_size: float = 0.10
    seed: int = 42
    label_names: Mapping[int, str] = field(
        default_factory=lambda: {0: "negative", 1: "positive"}
    )
    cache_dir: str | None = None

    def validate(self) -> None:
        """Validate configuration before any network or dataset operation."""

        if not self.name.strip():
            raise ValueError("dataset name must not be empty")
        if not self.config.strip():
            raise ValueError("dataset config must not be empty")
        if not self.revision.strip():
            raise ValueError("dataset revision must be pinned and non-empty")
        if not 0 < self.validation_size < 1:
            raise ValueError("validation_size must be between 0 and 1")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if not self.train_split.strip() or not self.test_split.strip():
            raise ValueError("train_split and test_split must not be empty")
        if self.train_split == self.test_split:
            raise ValueError("train_split and test_split must be different")
        if len(self.label_names) < 2:
            raise ValueError("at least two label names are required")

        keys = set(self.label_names)
        expected_keys = set(range(len(keys)))
        if keys != expected_keys:
            raise ValueError(
                "label_names keys must be contiguous integers starting at zero"
            )
        if any(not str(name).strip() for name in self.label_names.values()):
            raise ValueError("label names must not be empty")
        if len(set(self.label_names.values())) != len(self.label_names):
            raise ValueError("label names must be unique")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "DatasetConfig":
        """Build a config from the ``dataset`` section of a YAML-like mapping."""

        label_values = values.get("label_names", {0: "negative", 1: "positive"})
        if not isinstance(label_values, Mapping):
            raise ValueError("dataset.label_names must be a mapping")

        labels: dict[int, str] = {}
        for key, value in label_values.items():
            try:
                label_key = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid label key: {key!r}") from exc
            labels[label_key] = str(value)

        config = cls(
            name=str(values.get("name", DEFAULT_DATASET_NAME)),
            config=str(values.get("config", DEFAULT_DATASET_CONFIG)),
            revision=str(values.get("revision", DEFAULT_DATASET_REVISION)),
            train_split=str(values.get("train_split", "train")),
            test_split=str(values.get("test_split", "test")),
            validation_size=float(values.get("validation_size", 0.10)),
            seed=int(values.get("seed", 42)),
            label_names=labels,
            cache_dir=(
                None
                if values.get("cache_dir") in (None, "")
                else str(values["cache_dir"])
            ),
        )
        config.validate()
        return config


def load_config_file(path: str | Path) -> DatasetConfig:
    """Load ``dataset`` configuration from YAML without hiding parse errors."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "PyYAML is required to read the training configuration. "
            "Install the project data dependencies first."
        ) from exc

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}

    if not isinstance(document, Mapping):
        raise ValueError("configuration root must be a mapping")
    dataset_values = document.get("dataset", document)
    if not isinstance(dataset_values, Mapping):
        raise ValueError("configuration dataset section must be a mapping")
    return DatasetConfig.from_mapping(dataset_values)


def _load_split(config: DatasetConfig, split_name: str) -> Any:
    """Load one labeled split from the pinned Hugging Face revision."""

    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "The 'datasets' package is required to download the IMDb dataset."
        ) from exc

    return load_dataset(
        path=config.name,
        name=config.config,
        revision=config.revision,
        split=split_name,
        cache_dir=config.cache_dir,
    )


def _validate_split_schema(dataset: Any, split_name: str, config: DatasetConfig) -> None:
    required_columns = {"text", "label"}
    missing = required_columns.difference(dataset.column_names)
    if missing:
        raise ValueError(
            f"dataset split {split_name!r} is missing columns: {sorted(missing)}"
        )

    labels = {int(value) for value in dataset.unique("label")}
    expected = set(config.label_names)
    if labels != expected:
        raise ValueError(
            f"dataset split {split_name!r} labels {sorted(labels)} do not match "
            f"configured labels {sorted(expected)}"
        )

    if any(not isinstance(text, str) or not text.strip() for text in dataset["text"]):
        raise ValueError(f"dataset split {split_name!r} contains empty or non-string text")


def build_dataset(config: DatasetConfig) -> Any:
    """Return train, validation, and untouched test splits.

    Validation is a stratified sample of the source train split. The source test
    split remains isolated and is not shuffled or sampled here.
    """

    config.validate()
    train = _load_split(config, config.train_split)
    test = _load_split(config, config.test_split)

    _validate_split_schema(train, config.train_split, config)
    _validate_split_schema(test, config.test_split, config)

    # IMDb is provided with a ClassLabel feature, which makes this split
    # stratification explicit instead of relying on an accidental class balance.
    try:
        derived = train.train_test_split(
            test_size=config.validation_size,
            seed=config.seed,
            stratify_by_column="label",
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "Could not create a stratified validation split. The dataset must "
            "provide a ClassLabel-compatible 'label' column."
        ) from exc

    from datasets import DatasetDict

    result = DatasetDict(
        {
            "train": derived["train"],
            "validation": derived["test"],
            "test": test,
        }
    )
    for split_name, split in result.items():
        _validate_split_schema(split, split_name, config)
    return result


def class_distribution(dataset: Any, config: DatasetConfig) -> dict[str, dict[str, int]]:
    """Return human-readable label counts for every split."""

    config.validate()
    distributions: dict[str, dict[str, int]] = {}
    for split_name, split in dataset.items():
        counts = Counter(int(label) for label in split["label"])
        distributions[split_name] = {
            config.label_names[label]: counts.get(label, 0)
            for label in sorted(config.label_names)
        }
    return distributions


def dataset_metadata(dataset: Any, config: DatasetConfig) -> dict[str, Any]:
    """Create serializable provenance metadata for MLflow/artifact logging."""

    config.validate()
    return {
        "dataset_name": config.name,
        "dataset_config": config.config,
        "dataset_revision": config.revision,
        "source_url": DEFAULT_SOURCE_URL,
        "dataset_card_url": DEFAULT_DATASET_CARD_URL,
        "citation_url": DEFAULT_CITATION_URL,
        "validation_strategy": "stratified split from source train split",
        "validation_size": config.validation_size,
        "seed": config.seed,
        "label_names": {str(key): value for key, value in config.label_names.items()},
        "splits": {
            split_name: {"num_examples": split.num_rows}
            for split_name, split in dataset.items()
        },
        "class_distribution": class_distribution(dataset, config),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="training/config.yaml",
        help="path to the YAML training configuration",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        help="optional path for JSON dataset provenance metadata",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_config_file(args.config)
    dataset = build_dataset(config)
    metadata = dataset_metadata(dataset, config)
    rendered = json.dumps(metadata, indent=2, sort_keys=True)

    if args.metadata_path:
        args.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_path.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by CLI verification
    raise SystemExit(main())
