from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
K8S_ROOT = ROOT / "k8s"


def _documents(path: Path):
    return [document for document in yaml.safe_load_all(path.read_text()) if document]


def test_all_kubernetes_yaml_is_parseable_and_references_existing_base_files():
    paths = sorted(K8S_ROOT.rglob("*.yaml"))
    assert paths

    for path in paths:
        documents = _documents(path)
        assert documents, path
        for document in documents:
            assert "apiVersion" in document, path
            assert "kind" in document, path
            if document["kind"] != "Kustomization":
                assert "metadata" in document, path

    for overlay in (K8S_ROOT / "overlays" / "local", K8S_ROOT / "overlays" / "aws"):
        kustomization = yaml.safe_load(
            (overlay / "kustomization.yaml").read_text(encoding="utf-8")
        )
        for resource in kustomization["resources"]:
            if resource.startswith("../") or resource.startswith("../../"):
                resolved = (overlay / resource).resolve()
                if resolved.is_dir():
                    assert (resolved / "kustomization.yaml").exists()
                else:
                    assert resolved.exists(), resource


def test_base_deployment_is_readiness_gated_and_hardened():
    deployment = _documents(K8S_ROOT / "base" / "deployment.yaml")[0]
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]

    assert deployment["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == 0
    assert pod["securityContext"] == {
        "runAsNonRoot": True,
        "runAsUser": 10001,
        "runAsGroup": 10001,
        "fsGroup": 10001,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    assert pod["automountServiceAccountToken"] is False
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert container["startupProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["resources"]["requests"]
    assert container["resources"]["limits"]


def test_production_model_and_observability_configuration_are_explicit():
    configmap = _documents(K8S_ROOT / "base" / "configmap.yaml")[0]
    data = configmap["data"]

    assert data["MODEL_SOURCE"] == "mlflow"
    assert data["MLFLOW_MODEL_URI"] == (
        "models:/customer-feedback-classifier@production"
    )
    assert data["OTEL_TRACES_EXPORTER"] == "none"
    assert data["HF_HOME"] == "/tmp/huggingface"

    aws_patch = _documents(K8S_ROOT / "overlays" / "aws" / "configmap-patch.yaml")[0]
    assert aws_patch["data"]["OTEL_TRACES_EXPORTER"] == "otlp"
    assert "MLFLOW_TRACKING_URI" in aws_patch["data"]


def test_no_credentials_or_secret_objects_are_committed():
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in K8S_ROOT.rglob("*.yaml")
    )

    assert "kind: Secret" not in serialized
    assert "AWS_ACCESS_KEY_ID" not in serialized
    assert "AWS_SECRET_ACCESS_KEY" not in serialized
    assert "-----BEGIN PRIVATE KEY-----" not in serialized


def test_aws_overlay_requires_environment_specific_replacements():
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (K8S_ROOT / "overlays" / "aws").rglob("*.yaml")
    )

    for placeholder in (
        "REPLACE_WITH_ECR_REGISTRY",
        "REPLACE_WITH_GIT_SHA",
        "REPLACE_WITH_MLFLOW_TRACKING_URI",
        "REPLACE_WITH_IAM_ROLE_ARN",
        "REPLACE_WITH_ACM_CERTIFICATE_ARN",
        "REPLACE_WITH_API_HOSTNAME",
    ):
        assert placeholder in serialized
