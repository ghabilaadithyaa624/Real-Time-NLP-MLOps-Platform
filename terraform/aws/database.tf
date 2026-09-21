resource "aws_db_subnet_group" "mlflow" {
  name       = "${var.project_name}-${var.environment}-mlflow"
  subnet_ids = module.vpc.database_subnets

  tags = {
    Name = "${var.project_name}-${var.environment}-mlflow"
  }
}

resource "aws_security_group" "mlflow_db" {
  name        = "${var.project_name}-${var.environment}-mlflow-db"
  description = "Private PostgreSQL access from EKS nodes only"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "PostgreSQL from EKS node security group"
    protocol        = "tcp"
    from_port       = 5432
    to_port         = 5432
    security_groups = [module.eks.node_security_group_id]
  }

  egress {
    description = "Allow database response traffic"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "mlflow" {
  identifier = "${var.project_name}-${var.environment}-mlflow"

  engine               = "postgres"
  engine_version       = var.db_engine_version
  instance_class       = var.db_instance_class
  allocated_storage    = 50
  max_allocated_storage = 200
  storage_type         = "gp3"
  storage_encrypted    = true
  kms_key_id           = local.artifacts_kms_key_arn

  db_name  = var.db_name
  username = var.db_username
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.mlflow.name
  vpc_security_group_ids = [aws_security_group.mlflow_db.id]
  publicly_accessible    = false

  multi_az                  = var.db_multi_az
  backup_retention_period   = var.db_backup_retention_days
  copy_tags_to_snapshot    = true
  deletion_protection      = true
  skip_final_snapshot      = false
  final_snapshot_identifier = "${var.project_name}-${var.environment}-mlflow-final"
  apply_immediately        = false
  auto_minor_version_upgrade = true

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
}
