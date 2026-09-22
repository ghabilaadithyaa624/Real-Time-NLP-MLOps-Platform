from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load_workflow(name: str):
    return yaml.load(
        (WORKFLOWS / name).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def _actions(workflow: dict) -> list[str]:
    values: list[str] = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "uses" in step:
                values.append(step["uses"])
    return values


def test_ci_workflow_is_read_only_and_runs_validation_and_image_build():
    workflow = _load_workflow("ci.yml")

    assert workflow["permissions"]["contents"] == "read"
    assert "id-token" not in workflow["permissions"]
    assert set(workflow["jobs"]) == {"validate", "docker"}
    assert workflow["jobs"]["docker"]["needs"] == "validate"
    ci_text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "push: false" in ci_text
    assert "load: true" in ci_text
    assert "aquasecurity/trivy-action@0.29.0" in ci_text
    assert "anchore/sbom-action@v0.17.0" in ci_text
    assert "ruff check app training tests" in ci_text
    assert "bandit --quiet --recursive app training" in ci_text
    assert "python -m pytest --quiet tests" in ci_text


def test_release_workflow_uses_oidc_and_sha_tagged_images():
    workflow = _load_workflow("release.yml")

    assert workflow["permissions"]["contents"] == "read"
    assert workflow["permissions"]["id-token"] == "write"
    assert workflow["jobs"]["release"]["environment"] == "production"
    release_text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "configure-aws-credentials" in release_text
    assert "role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}" in release_text
    assert "${{ github.sha }}" in release_text
    assert "REPLACE_WITH_" in release_text
    assert "WAF_ACL_ARN" in release_text
    assert "kubectl rollout status" in release_text
    assert "kubectl apply --dry-run=server" in release_text
    assert "aquasecurity/trivy-action@0.29.0" in release_text
    assert "anchore/sbom-action@v0.17.0" in release_text
    assert ":latest" not in release_text


def test_workflow_actions_use_versioned_references_and_no_static_credentials():
    for workflow_name in ("ci.yml", "release.yml"):
        workflow = _load_workflow(workflow_name)
        for action in _actions(workflow):
            assert "@latest" not in action
            assert "@main" not in action
            assert "@master" not in action
            assert "@v" in action or "@" in action

    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml")
    )
    assert "AWS_ACCESS_KEY_ID:" not in serialized
    assert "AWS_SECRET_ACCESS_KEY:" not in serialized
    assert "-----BEGIN PRIVATE KEY-----" not in serialized


def test_development_dependencies_pin_ci_tools():
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "ruff==0.9.10" in requirements
    assert "bandit==1.8.3" in requirements
