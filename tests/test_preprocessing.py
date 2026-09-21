from datasets import ClassLabel, Dataset, DatasetDict, Features, Value
import pytest

from app.inference.preprocessing import (
    PreprocessingConfig,
    PreprocessingError,
    normalize_text,
    tokenize_batch,
    tokenize_dataset,
)


class FakeTokenizer:
    def __init__(self):
        self.calls = []

    def __call__(
        self,
        texts,
        *,
        padding,
        truncation,
        max_length,
        return_attention_mask,
    ):
        self.calls.append(
            {
                "texts": list(texts),
                "padding": padding,
                "truncation": truncation,
                "max_length": max_length,
                "return_attention_mask": return_attention_mask,
            }
        )
        return {
            "input_ids": [[index + 1] * max_length for index, _ in enumerate(texts)],
            "attention_mask": [[1] * max_length for _ in texts],
        }


def test_normalization_is_deterministic_without_lowercasing():
    assert normalize_text("  Café\u00a0quality\nwas excellent!  ") == (
        "Café quality was excellent!"
    )


def test_empty_text_is_rejected():
    with pytest.raises(PreprocessingError, match="empty"):
        normalize_text(" \n\t ")


def test_tokenization_uses_fixed_padding_and_truncation():
    tokenizer = FakeTokenizer()
    config = PreprocessingConfig(max_length=6)

    encoded = tokenize_batch(tokenizer, ["Great product", "Needs work"], config)

    assert set(encoded) == {"input_ids", "attention_mask"}
    assert all(len(row) == 6 for row in encoded["input_ids"])
    assert tokenizer.calls == [
        {
            "texts": ["Great product", "Needs work"],
            "padding": "max_length",
            "truncation": True,
            "max_length": 6,
            "return_attention_mask": True,
        }
    ]


def test_dataset_tokenization_preserves_labels():
    features = Features(
        {"text": Value("string"), "label": ClassLabel(names=["neg", "pos"])}
    )
    dataset = Dataset.from_dict(
        {"text": ["positive", "negative"], "label": [1, 0]},
        features=features,
    )
    tokenized = tokenize_dataset(dataset, FakeTokenizer(), PreprocessingConfig(max_length=4))

    assert "text" not in tokenized.column_names
    assert tokenized.column_names == ["label", "input_ids", "attention_mask"]
    assert tokenized["label"] == [1, 0]
    assert all(len(row) == 4 for row in tokenized["input_ids"])


def test_dataset_dict_tokenization_handles_each_split():
    features = Features(
        {"text": Value("string"), "label": ClassLabel(names=["neg", "pos"])}
    )
    dataset = Dataset.from_dict(
        {"text": ["positive", "negative"], "label": [1, 0]},
        features=features,
    )
    tokenized = tokenize_dataset(
        DatasetDict({"train": dataset, "validation": dataset}),
        FakeTokenizer(),
        PreprocessingConfig(max_length=4),
    )

    assert set(tokenized) == {"train", "validation"}
    assert all("text" not in split.column_names for split in tokenized.values())
    assert all(
        len(row) == 4
        for split in tokenized.values()
        for row in split["attention_mask"]
    )
