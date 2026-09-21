# Model governance and promotion

## Lifecycle states

```text
candidate
   |
   | validation report + provenance checks + F1 threshold
   |
   +--> validated --explicit promotion--> production
   |
   +--> rejected
```

A model version is registered as `candidate`. It cannot receive the `production` alias until it has:

- a `READY` MLflow model version;
- a validation-split evaluation report;
- F1 at or above `governance.minimum_f1`;
- a report tied to the registered training run;
- a matching dataset revision;
- recorded evaluation evidence.

## Validation

```bash
.venv/bin/python -m training.promote_model validate \
  --config training/config.yaml \
  --model-name customer-feedback-classifier \
  --version <VERSION> \
  --evaluation-report artifacts/evaluation-validation/evaluation_report.json
```

A passing validation operation:

- sets the model-version lifecycle tag to `validated`;
- assigns the `validated` alias;
- records validation F1;
- records the minimum threshold;
- records validation timestamp;
- records evaluation report SHA-256;
- records evaluation Git commit;
- records dataset revision.

A failing validation operation:

- sets lifecycle status to `rejected`;
- assigns the `rejected` alias;
- removes the candidate alias for that version;
- exits with a non-zero status from the CLI.

The validation command does not assign `production`.

## Production promotion

```bash
.venv/bin/python -m training.promote_model promote \
  --config training/config.yaml \
  --model-name customer-feedback-classifier \
  --version <VALIDATED_VERSION>
```

Promotion is refused unless:

```text
lifecycle_status == validated
validated alias points to requested version
```

On success, MLflow receives:

```text
@production alias
promotion timestamp
promoted_by
previous production version
model type
model Git commit
model dataset revision
```

MLflow aliases are used instead of deprecated stage transitions.

## Auditability

The following metadata is recorded on model versions:

```text
model version
model type
validation F1
minimum F1
validation timestamp
promotion timestamp
source run ID
dataset revision
Git commit
evaluation report hash
lifecycle status
```

The evaluation report hash prevents a governance record from silently referring to a different local report file later.

## Safety properties

- A test-set report cannot be used as the validation gate.
- An evaluation report from another training run is rejected.
- A mismatched dataset revision is rejected.
- A model without a source training run is rejected.
- A candidate cannot be promoted directly.
- A rejected model cannot be promoted.
- Promotion is a separate explicit command.
