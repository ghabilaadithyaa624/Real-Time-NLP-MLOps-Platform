# NLP preprocessing

## Design

Training and serving share the same preprocessing module at `app/inference/preprocessing.py`. This prevents a common production failure mode where the model is trained with one normalization/tokenization policy and served with another.

The current policy is intentionally minimal:

1. Apply Unicode NFKC normalization.
2. Collapse repeated whitespace and trim leading/trailing whitespace.
3. Preserve case and punctuation for the pretrained tokenizer.
4. Tokenize with the configured Hugging Face tokenizer.
5. Pad every sequence to the configured maximum length.
6. Truncate sequences longer than the maximum length.
7. Return `input_ids` and `attention_mask`.

No word-level stop-word removal, stemming, or manual lowercasing is performed. Those operations could remove sentiment-bearing signals or diverge from the pretrained tokenizer's vocabulary behavior.

## Configuration

`training/config.yaml` currently defines:

```yaml
model:
  name: distilbert-base-uncased
  revision: 12040accade4e8a0f71eabdb258fecc2e7e948be

preprocessing:
  max_length: 128
  padding: max_length
  truncation: true
```

`max_length: 128` is a starting point that limits CPU/GPU memory and latency while covering most short feedback. It remains configuration-driven so the training and serving trade-off can be measured later. A model-specific maximum must be respected when changing this value.

The tokenizer loader uses `AutoTokenizer`, not a DistilBERT-specific class. This keeps model replacement configuration-driven.

## Dataset integration

`tokenize_dataset` accepts a Hugging Face `Dataset` or `DatasetDict` and maps tokenization in batches. It removes the raw `text` field from the tokenized training representation while preserving `label`.

The tokenization call explicitly sets:

```python
tokenizer(
    texts,
    padding="max_length",
    truncation=True,
    max_length=max_length,
    return_attention_mask=True,
)
```

The implementation validates that every returned field has the expected batch size and fixed sequence length.

## Model and tokenizer provenance

The initial tokenizer is DistilBERT uncased. Its model revision is pinned in configuration for reproducibility. Model artifacts are not downloaded during tests and are not committed to Git.
