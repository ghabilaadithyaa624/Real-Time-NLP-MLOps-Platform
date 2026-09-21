from unittest.mock import patch

import pytest
from datasets import ClassLabel, Dataset, Features, Value

from training.dataset import DatasetConfig, build_dataset, class_distribution, dataset_metadata


@pytest.fixture
def local_splits():
    features = Features(
        {"text": Value("string"), "label": ClassLabel(names=["neg", "pos"])}
    )
    train = Dataset.from_dict(
        {
            "text": [f"training review {index}" for index in range(20)],
            "label": [index % 2 for index in range(20)],
        },
        features=features,
    )
    test = Dataset.from_dict(
        {
            "text": [f"test review {index}" for index in range(10)],
            "label": [index % 2 for index in range(10)],
        },
        features=features,
    )
    return train, test


def test_config_requires_a_pinned_revision():
    with pytest.raises(ValueError, match="revision"):
        DatasetConfig(revision="").validate()


def test_build_dataset_is_stratified_and_preserves_test_split(local_splits):
    config = DatasetConfig(validation_size=0.2, seed=42)
    with patch("training.dataset._load_split", side_effect=local_splits):
        dataset = build_dataset(config)

    assert {name: split.num_rows for name, split in dataset.items()} == {
        "train": 16,
        "validation": 4,
        "test": 10,
    }
    assert class_distribution(dataset, config) == {
        "train": {"negative": 8, "positive": 8},
        "validation": {"negative": 2, "positive": 2},
        "test": {"negative": 5, "positive": 5},
    }


def test_metadata_contains_provenance(local_splits):
    config = DatasetConfig(validation_size=0.2, seed=42)
    with patch("training.dataset._load_split", side_effect=local_splits):
        dataset = build_dataset(config)

    metadata = dataset_metadata(dataset, config)
    assert metadata["dataset_name"] == "stanfordnlp/imdb"
    assert metadata["dataset_revision"] == config.revision
    assert metadata["splits"]["validation"]["num_examples"] == 4
    assert metadata["class_distribution"]["test"] == {
        "negative": 5,
        "positive": 5,
    }
