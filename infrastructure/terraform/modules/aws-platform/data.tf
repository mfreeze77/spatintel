resource "random_password" "valkey" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "valkey" {
  name_prefix             = "${local.prefix}/valkey-"
  kms_key_id              = aws_kms_key.platform.arn
  recovery_window_in_days = 30
  tags                    = local.tags
}
resource "aws_secretsmanager_secret_version" "valkey" {
  secret_id = aws_secretsmanager_secret.valkey.id
  secret_string = jsonencode({
    auth_token = random_password.valkey.result
  })
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.prefix}-database"
  subnet_ids = aws_subnet.data[*].id
  tags       = local.tags
}
resource "aws_security_group" "database" {
  name_prefix = "${local.prefix}-database-"
  description = "PostgreSQL from EKS workloads only"
  vpc_id      = aws_vpc.this.id
  ingress {
    protocol        = "tcp"
    from_port       = 5432
    to_port         = 5432
    security_groups = [aws_eks_cluster.this.vpc_config[0].cluster_security_group_id]
  }
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
resource "aws_db_parameter_group" "this" {
  name_prefix = "${local.prefix}-pg18-"
  family      = "postgres18"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  parameter {
    name  = "log_connections"
    value = "all"
  }
  parameter {
    name  = "log_disconnections"
    value = "1"
  }
  parameter {
    name  = "log_lock_waits"
    value = "1"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements,pgaudit"
    apply_method = "pending-reboot"
  }
  tags = local.tags
  lifecycle {
    create_before_destroy = true
  }
}
resource "aws_iam_role" "rds_monitoring" {
  name = "${local.prefix}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}
resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
resource "aws_db_instance" "this" {
  identifier_prefix                   = "${local.prefix}-"
  engine                              = "postgres"
  engine_version                      = var.database_engine_version
  instance_class                      = var.database_instance_class
  allocated_storage                   = var.database_allocated_storage_gib
  max_allocated_storage               = var.database_max_allocated_storage_gib
  storage_type                        = "gp3"
  storage_encrypted                   = true
  kms_key_id                          = aws_kms_key.platform.arn
  db_name                             = "sip"
  username                            = "sip_admin"
  manage_master_user_password         = true
  master_user_secret_kms_key_id       = aws_kms_key.platform.arn
  port                                = 5432
  multi_az                            = true
  publicly_accessible                 = false
  db_subnet_group_name                = aws_db_subnet_group.this.name
  vpc_security_group_ids              = [aws_security_group.database.id]
  parameter_group_name                = aws_db_parameter_group.this.name
  backup_retention_period             = var.database_backup_retention_days
  backup_window                       = "03:00-04:00"
  maintenance_window                  = "sun:05:00-sun:06:00"
  auto_minor_version_upgrade          = false
  allow_major_version_upgrade         = false
  deletion_protection                 = var.database_deletion_protection
  skip_final_snapshot                 = var.database_skip_final_snapshot
  final_snapshot_identifier           = var.database_skip_final_snapshot ? null : "${local.prefix}-final-${replace(var.database_engine_version, ".", "-")}"
  copy_tags_to_snapshot               = true
  enabled_cloudwatch_logs_exports     = ["postgresql", "upgrade"]
  performance_insights_enabled        = true
  performance_insights_kms_key_id     = aws_kms_key.platform.arn
  performance_insights_retention_period = 731
  monitoring_interval                 = 60
  monitoring_role_arn                 = aws_iam_role.rds_monitoring.arn
  iam_database_authentication_enabled = true
  apply_immediately                   = false
  tags                                = local.tags
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${local.prefix}-valkey"
  subnet_ids = aws_subnet.data[*].id
}
resource "aws_security_group" "valkey" {
  name_prefix = "${local.prefix}-valkey-"
  description = "Valkey from EKS workloads only"
  vpc_id      = aws_vpc.this.id
  ingress {
    protocol        = "tcp"
    from_port       = 6379
    to_port         = 6379
    security_groups = [aws_eks_cluster.this.vpc_config[0].cluster_security_group_id]
  }
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = substr("${local.prefix}-valkey", 0, 40)
  description                = "SIP durable queue and cache"
  engine                     = "valkey"
  engine_version             = var.valkey_engine_version
  node_type                  = var.valkey_node_type
  port                       = 6379
  num_cache_clusters         = 1 + var.valkey_replicas_per_node_group
  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"
  auth_token                 = random_password.valkey.result
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.valkey.id]
  snapshot_retention_limit   = 7
  snapshot_window            = "02:00-03:00"
  maintenance_window         = "sun:04:00-sun:05:00"
  auto_minor_version_upgrade = false
  apply_immediately          = false
  data_tiering_enabled       = false
  tags                       = local.tags
}
