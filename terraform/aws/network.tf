module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.21.0"

  name = "${var.project_name}-${var.environment}"
  cidr = var.vpc_cidr

  azs              = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets  = ["10.40.1.0/24", "10.40.2.0/24", "10.40.3.0/24"]
  public_subnets   = ["10.40.101.0/24", "10.40.102.0/24", "10.40.103.0/24"]
  database_subnets = ["10.40.201.0/24", "10.40.202.0/24", "10.40.203.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"
  enable_vpn_gateway = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  database_subnet_group_name = "${var.project_name}-${var.environment}"
}
