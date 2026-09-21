# Transformer training

## Training flow

```text
Pinned IMDb dataset
  |
  v
Deterministic train/validation/test split
  |
  v
Shared preprocessing and tokenizer
  |
  v
AutoModelForSequenceClassification
  |
  v
Hugging Face Trainer
  |
  +-- CUDA when available
  +-- CPU fallback
  +-- validation metrics each epoch
  +-- checkpoint by validation F1
  |
  v
Best model + tokenizer + training_summary.json
```

The training script uses `AutoModelForSequenceClassification` and the model name from configuration. It does not hard-code DistilBERT layers into the training loop.

## Checkpoint policy

The best checkpoint is selected using validation macro F1:

```text
metric_for_best_model = f1
greater_is_better = true
load_best_model_at_end = true
```

The source test set remains untouched until the evaluation phase.

## Reproducibility

The training summary records:

- Git commit;
- model name and revision;
- dataset name, revision, and split metadata;
- label mapping;
- maximum sequence length;
- batch size;
- learning rate;
- epoch count;
- random seed;
- selected device;
- PyTorch version;
- best checkpoint;
- train and validation metrics;
- per-step loss and learning-rate history from the Trainer.

Python, NumPy, and PyTorch random generators are seeded. CUDA deterministic settings are enabled where available. Exact bit-for-bit reproducibility can still depend on hardware and kernel implementations, so the environment and software versions are recorded as part of the run.

## CPU and CUDA behavior

The script checks `torch.cuda.is_available()`:

- CUDA is used automatically when available;
- CPU mode is selected otherwise;
- mixed precision is only enabled when configured and CUDA is available.

No CUDA device is assumed.

## Commands

Configuration validation:

```bash
.venv/bin/python - <<'PY'
from training.config import load_experiment_config
config = load_experiment_config("training/config.yaml")
print(config)
PY
```

Full training, when the pinned dataset and model are available locally or through the configured network:

```bash
.venv/bin/python -m training.train \
  --config training/config.yaml \
  --output-dir artifacts/training
```

A small smoke run can limit the number of examples without changing the production configuration:

```bash
.venv/bin/python -m training.train \
  --config training/config.yaml \
  --output-dir /tmp/nlp-training-smoke \
  --max-train-samples 32 \
  --max-eval-samples 16
```

The smoke-run option is for pipeline verification only. It must not be used as a production model-training result.

## MLflow boundary

This phase writes local run summaries. MLflow tracking, artifact logging, model registration, and model promotion are intentionally implemented in later phases so each lifecycle boundary remains explicit.
