output "vpc_id" {
  value = aws_vpc.this.id
}
output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
output "data_subnet_ids" {
  value = aws_subnet.data[*].id
}
output "eks_cluster_name" {
  value = aws_eks_cluster.this.name
}
output "eks_cluster_endpoint" {
  value     = aws_eks_cluster.this.endpoint
  sensitive = true
}
output "ecr_repository_url" {
  value = aws_ecr_repository.application.repository_url
}
output "evidence_bucket" {
  value = aws_s3_bucket.evidence.id
}
output "exports_bucket" {
  value = aws_s3_bucket.exports.id
}
output "database_endpoint" {
  value     = aws_db_instance.this.address
  sensitive = true
}
output "database_secret_arn" {
  value = aws_db_instance.this.master_user_secret[0].secret_arn
}
output "valkey_endpoint" {
  value     = aws_elasticache_replication_group.this.primary_endpoint_address
  sensitive = true
}
output "valkey_secret_arn" {
  value = aws_secretsmanager_secret.valkey.arn
}
output "platform_kms_key_arn" {
  value = aws_kms_key.platform.arn
}
output "audit_kms_key_arn" {
  value = aws_kms_key.audit.arn
}
output "api_role_arns" {
  value = { for key, role in aws_iam_role.api : key => role.arn }
}
output "worker_role_arns" {
  value = { for key, role in aws_iam_role.worker : key => role.arn }
}
