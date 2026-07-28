resource "aws_backup_vault" "this" {
  name          = local.prefix
  kms_key_arn   = aws_kms_key.audit.arn
  force_destroy = false
  tags          = local.tags
}
resource "aws_backup_vault_lock_configuration" "this" {
  backup_vault_name   = aws_backup_vault.this.name
  min_retention_days  = 35
  max_retention_days  = 3650
  changeable_for_days = 3
}
resource "aws_backup_plan" "this" {
  name = local.prefix
  rule {
    rule_name         = "daily"
    target_vault_name = aws_backup_vault.this.name
    schedule          = "cron(0 6 ? * * *)"
    start_window      = 60
    completion_window = 360
    lifecycle {
      cold_storage_after = 90
      delete_after       = 3650
    }
    recovery_point_tags = local.tags
  }
  tags = local.tags
}
resource "aws_iam_role" "backup" {
  name = "${local.prefix}-backup"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "backup.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}
resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}
resource "aws_backup_selection" "database" {
  iam_role_arn = aws_iam_role.backup.arn
  name         = "${local.prefix}-database"
  plan_id      = aws_backup_plan.this.id
  resources    = [aws_db_instance.this.arn]
}

resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${local.prefix}-database-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "breaching"
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.identifier
  }
  tags = local.tags
}
resource "aws_cloudwatch_metric_alarm" "database_storage" {
  alarm_name          = "${local.prefix}-database-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Minimum"
  threshold           = 21474836480
  treat_missing_data  = "breaching"
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.identifier
  }
  tags = local.tags
}
resource "aws_cloudwatch_metric_alarm" "valkey_memory" {
  alarm_name          = "${local.prefix}-valkey-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Maximum"
  threshold           = 80
  treat_missing_data  = "breaching"
  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.this.replication_group_id
  }
  tags = local.tags
}
