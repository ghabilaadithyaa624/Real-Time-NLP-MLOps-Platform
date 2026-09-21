from pathlib import Path

import pytest
from transformers import (
    DistilBertConfig,
    DistilBertForSequenceClassification,
    DistilBertTokenizerFast,
)


@pytest.fixture(scope="session")
def tiny_model_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a deterministic local model for integration tests only."""

    path = tmp_path_factory.mktemp("tiny-model")
    (path / "vocab.txt").write_text(
        "[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\ngood\nbad\nmovie\nproduct\n",
        encoding="utf-8",
    )
    DistilBertTokenizerFast(vocab_file=str(path / "vocab.txt")).save_pretrained(path)
    config = DistilBertConfig(
        vocab_size=9,
        max_position_embeddings=16,
        n_layers=1,
        n_heads=2,
        dim=16,
        hidden_dim=32,
        num_labels=2,
        id2label={0: "negative", 1: "positive"},
        label2id={"negative": 0, "positive": 1},
    )
    DistilBertForSequenceClassification(config).save_pretrained(path)
    return path
