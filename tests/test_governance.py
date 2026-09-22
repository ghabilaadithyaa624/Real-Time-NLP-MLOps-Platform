from types import SimpleNamespace

from training.governance import governance_evidence


def _version():
    return SimpleNamespace(
        tags={
            "source_run_id": "run-123",
            "dataset_revision": "dataset-sha",
            "git_commit": "train-commit",
        }
    )


def _run():
    return SimpleNamespace(data=SimpleNamespace(tags={"dataset_revision": "dataset-sha"}))


def _report(f1=0.95, split="validation", run_id="run-123"):
    return {
        "git_commit": "eval-commit",
        "training_run_id": run_id,
        "split": split,
        "dataset": {"dataset_revision": "dataset-sha"},
        "evaluation": {"metrics": {"f1": f1}},
    }


def test_governance_accepts_validation_report_above_threshold():
    decision = governance_evidence(
        _report(), _version(), _run(), minimum_f1=0.90
    )

    assert decision["passed"] is True
    assert decision["observed_f1"] == 0.95


def test_governance_rejects_test_report_for_promotion():
    decision = governance_evidence(
        _report(split="test"), _version(), _run(), minimum_f1=0.90
    )

    assert decision["passed"] is False
    assert "validation split" in decision["reason"]


def test_governance_rejects_mismatched_training_run():
    decision = governance_evidence(
        _report(run_id="different-run"), _version(), _run(), minimum_f1=0.90
    )

    assert decision["passed"] is False
    assert "registered training run" in decision["reason"]


def test_governance_rejects_f1_below_threshold():
    decision = governance_evidence(
        _report(f1=0.89), _version(), _run(), minimum_f1=0.90
    )

    assert decision["passed"] is False
    assert "below" in decision["reason"]
