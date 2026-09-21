"""CLI for validation and deliberate MLflow production promotion."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from training.config import load_experiment_config
from training.governance import (
    GovernanceError,
    promote_validated_version,
    validate_model_version,
)
from training.mlflow_tracking import resolved_tracking_uri


def _base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", default="training/config.yaml")
    parser.add_argument("--model-name")
    parser.add_argument("--version", required=True)
    return parser


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate",
        parents=[_base_parser()],
        help="validate a candidate using a validation evaluation report",
    )
    validate.add_argument("--evaluation-report", required=True)

    subparsers.add_parser(
        "promote",
        parents=[_base_parser()],
        help="promote a validated version to the production alias",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_experiment_config(args.config)
    model_name = args.model_name or config.mlflow.registered_model_name
    tracking_uri = resolved_tracking_uri(config)

    try:
        if args.command == "validate":
            result = validate_model_version(
                tracking_uri=tracking_uri,
                model_name=model_name,
                version=args.version,
                evaluation_report=args.evaluation_report,
                minimum_f1=config.governance.minimum_f1,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["lifecycle_status"] == "validated" else 2

        result = promote_validated_version(
            tracking_uri=tracking_uri,
            model_name=model_name,
            version=args.version,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except GovernanceError as exc:
        print(f"governance error: {exc}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
