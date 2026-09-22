# Testing and validation

## Test layers

```text
Unit tests
  +-- preprocessing
  +-- tokenization contracts
  +-- metrics
  +-- configuration
  +-- governance decisions
  +-- inference settings

API tests
  +-- request validation
  +-- health/readiness
  +-- model metadata
  +-- response schema
  +-- error sanitization

Integration tests
  +-- real local tokenizer
  +-- real tiny Transformer
  +-- FastAPI TestClient
  +-- startup model behavior

Static checks
  +-- Python compilation
  +-- Dockerfile safety assertions
  +-- YAML parsing
```

## Commands

Install development dependencies:

```bash
make install
```

Run the full suite:

```bash
make test
```

Run coverage for application and training code:

```bash
make coverage
```

Run API-focused coverage:

```bash
make api-coverage
```

Compile-check Python files:

```bash
make compile
```

## Current verification

The full suite currently passes with 33 tests.

The critical API/inference surface has 82% line coverage, including:

- request validation;
- health and readiness behavior;
- local Transformer prediction;
- startup model failure;
- inference error sanitization;
- CPU inference mode;
- model sequence-length validation.

The combined application and training coverage is lower because command-line MLflow, training, evaluation, and registration workflows are primarily exercised through focused unit tests and explicit smoke tests. Those workflows are dependency- and artifact-heavy and are not hidden behind fabricated benchmark results.

## Test data policy

Tests create tiny deterministic Transformer fixtures in temporary directories. No datasets, model weights, MLflow state, or coverage artifacts are committed to Git.

## Failure behavior tested

- invalid JSON;
- missing request fields;
- extra request fields;
- empty text;
- overlong text;
- model load failure;
- readiness failure;
- inference failure without internal exception leakage;
- invalid tokenizer output;
- invalid governance evidence;
- rejected production promotion.
