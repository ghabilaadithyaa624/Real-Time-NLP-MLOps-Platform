from pathlib import Path

import hcl2


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = ROOT / "terraform" / "aws"


def _load(path: Path):
    with path.open(encoding="utf-8") as stream:
        return hcl2.load(stream)


def test_all_terraform_hcl_parses():
    paths = sorted(TERRAFORM_ROOT.glob("*.tf"))
    assert paths
    for path in paths:
        assert _load(path) is not None, path


def test_terraform_modules_and_provider_constraints_are_pinned():
    versions = _load(TERRAFORM_ROOT / "versions.tf")
    required = versions["terraform"][0]["required_providers"][0]
    assert required["aws"]["source"] == "hashicorp/aws"
    assert required["aws"]["version"] == "~> 5.92"
    assert required["random"]["version"] == "~> 3.7"

    network = _load(TERRAFORM_ROOT / "network.tf")
    eks = _load(TERRAFORM_ROOT / "eks.tf")
    assert network["module"][0]["vpc"]["version"] == "5.21.0"
    assert eks["module"][0]["eks"]["version"] == "20.37.1"


def test_eks_is_private_by_default_and_uses_workload_identity():
    variables = _load(TERRAFORM_ROOT / "variables.tf")
    variable_map = {
        name: value for item in variables["variable"] for name, value in item.items()
    }
    assert variable_map["cluster_endpoint_public_access"]["default"] is False
    assert "0.0.0.0/0" in variable_map["cluster_endpoint_public_access_cidrs"]["validation"][0]["condition"]

    eks = _load(TERRAFORM_ROOT / "eks.tf")["module"][0]["eks"]
    assert eks["enable_irsa"] is True
    assert eks["cluster_endpoint_private_access"] is True
    assert eks["enable_cluster_creator_admin_permissions"] is False

    iam = _load(TERRAFORM_ROOT / "iam.tf")
    serialized = str(iam)
    assert "AssumeRoleWithWebIdentity" in serialized
    assert "system:serviceaccount:${var.kubernetes_namespace}:${var.kubernetes_service_account}" in serialized


def test_artifacts_and_database_are_private_and_encrypted():
    artifacts = _load(TERRAFORM_ROOT / "artifacts.tf")
    resources = {
        resource_type: blocks
        for resource in artifacts["resource"]
        for resource_type, blocks in resource.items()
    }
    assert "aws_s3_bucket_public_access_block" in resources
    block = resources["aws_s3_bucket_public_access_block"]["artifacts"]
    assert block["block_public_acls"] is True
    assert block["block_public_policy"] is True
    assert block["restrict_public_buckets"] is True
    assert "aws_s3_bucket_versioning" in resources
    assert "aws_s3_bucket_server_side_encryption_configuration" in resources

    database_resources = {
        resource_type: blocks
        for resource in _load(TERRAFORM_ROOT / "database.tf")["resource"]
        for resource_type, blocks in resource.items()
    }
    database = database_resources["aws_db_instance"]["mlflow"]
    assert database["publicly_accessible"] is False
    assert database["storage_encrypted"] is True
    assert database["manage_master_user_password"] is True
    assert database["deletion_protection"] is True


def test_waf_rate_limiting_and_common_rules_are_configured():
    waf_resources = {
        resource_type: blocks
        for resource in _load(TERRAFORM_ROOT / "waf.tf")["resource"]
        for resource_type, blocks in resource.items()
    }
    waf = waf_resources["aws_wafv2_web_acl"]["api"]
    assert waf["scope"] == "REGIONAL"
    assert waf["default_action"][0]["allow"] == [{}]
    rate_rule = next(rule for rule in waf["rule"] if rule["name"] == "rate-limit-by-ip")
    rate_statement = rate_rule["statement"][0]["rate_based_statement"][0]
    assert rate_statement["aggregate_key_type"] == "IP"
    managed_rule = next(
        rule for rule in waf["rule"] if rule["name"] == "aws-managed-common-rules"
    )
    assert managed_rule["statement"][0]["managed_rule_group_statement"][0]["vendor_name"] == "AWS"


def test_ecr_is_immutable_and_terraform_state_is_ignored():
    ecr_resources = {
        resource_type: blocks
        for resource in _load(TERRAFORM_ROOT / "ecr.tf")["resource"]
        for resource_type, blocks in resource.items()
    }
    ecr = ecr_resources["aws_ecr_repository"]["api"]
    assert ecr["image_tag_mutability"] == "IMMUTABLE"
    assert ecr["image_scanning_configuration"][0]["scan_on_push"] is True

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (".terraform/", "*.tfstate", "*.tfplan", "backend.tf"):
        assert entry in gitignore


def test_terraform_files_contain_no_static_credentials():
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in TERRAFORM_ROOT.glob("*.tf")
    )
    assert "AWS_ACCESS_KEY_ID" not in serialized
    assert "AWS_SECRET_ACCESS_KEY" not in serialized
    assert "-----BEGIN PRIVATE KEY-----" not in serialized
    assert 'password = "' not in serialized
