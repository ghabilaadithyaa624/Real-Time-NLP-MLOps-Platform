"""Deterministic text normalization and Transformer tokenization.

This module is shared by offline training and online inference. Keeping the
normalization and tokenizer call in one place prevents training/serving skew.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class PreprocessingError(ValueError):
    """Raised when input cannot be deterministically preprocessed."""


@dataclass(frozen=True)
class PreprocessingConfig:
    """Tokenization behavior shared by training and serving."""

    max_length: int = 128
    padding: str = "max_length"
    truncation: bool = True

    def validate(self) -> None:
        if isinstance(self.max_length, bool) or not isinstance(self.max_length, int):
            raise ValueError("max_length must be an integer")
        if self.max_length <= 0:
            raise ValueError("max_length must be greater than zero")
        if self.padding != "max_length":
            raise ValueError("padding must be 'max_length' for fixed-size batches")
        if self.truncation is not True:
            raise ValueError("truncation must be enabled")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "PreprocessingConfig":
        config = cls(
            max_length=int(values.get("max_length", 128)),
            padding=str(values.get("padding", "max_length")),
            truncation=bool(values.get("truncation", True)),
        )
        config.validate()
        return config


def normalize_text(text: str) -> str:
    """Apply a minimal, deterministic normalization policy.

    Unicode compatibility normalization and whitespace collapsing remove
    transport-level variation without lowercasing or removing punctuation.
    Lowercasing is left to the pretrained tokenizer's own vocabulary policy.
    """

    if not isinstance(text, str):
        raise PreprocessingError("text must be a string")

    normalized = unicodedata.normalize("NFKC", text)
    normalized = " ".join(normalized.split())
    if not normalized:
        raise PreprocessingError("text must not be empty after normalization")
    return normalized


def normalize_texts(texts: Sequence[str]) -> list[str]:
    """Normalize a non-empty batch while preserving order."""

    if not texts:
        raise PreprocessingError("at least one text input is required")
    return [normalize_text(text) for text in texts]


def tokenize_batch(
    tokenizer: Any,
    texts: Sequence[str],
    config: PreprocessingConfig,
) -> dict[str, Any]:
    """Tokenize text with explicit padding, truncation, and attention masks."""

    config.validate()
    normalized = normalize_texts(texts)
    encoded = tokenizer(
        normalized,
        padding=config.padding,
        truncation=config.truncation,
        max_length=config.max_length,
        return_attention_mask=True,
    )

    if not isinstance(encoded, Mapping):
        raise PreprocessingError("tokenizer must return a mapping of encoded fields")

    required_fields = {"input_ids", "attention_mask"}
    missing_fields = required_fields.difference(encoded)
    if missing_fields:
        raise PreprocessingError(
            f"tokenizer output is missing fields: {sorted(missing_fields)}"
        )

    batch_size = len(normalized)
    for field_name, values in encoded.items():
        if len(values) != batch_size:
            raise PreprocessingError(
                f"tokenizer field {field_name!r} has an invalid batch size"
            )
        for row in values:
            if len(row) != config.max_length:
                raise PreprocessingError(
                    f"tokenizer field {field_name!r} is not padded to max_length"
                )

    return dict(encoded)


def tokenize_dataset(dataset: Any, tokenizer: Any, config: PreprocessingConfig) -> Any:
    """Tokenize a Hugging Face Dataset or DatasetDict without changing labels."""

    config.validate()
    columns = dataset.column_names
    if isinstance(columns, Mapping):
        missing_text = [
            split_name
            for split_name, split_columns in columns.items()
            if "text" not in split_columns
        ]
        if missing_text:
            raise PreprocessingError(
                "dataset splits must contain a 'text' column: "
                f"{sorted(missing_text)}"
            )
    elif "text" not in columns:
        raise PreprocessingError("dataset must contain a 'text' column")

    def tokenize_examples(batch: Mapping[str, Sequence[str]]) -> dict[str, Any]:
        return tokenize_batch(tokenizer, batch["text"], config)

    return dataset.map(
        tokenize_examples,
        batched=True,
        remove_columns=["text"],
        desc="Tokenizing text",
    )
