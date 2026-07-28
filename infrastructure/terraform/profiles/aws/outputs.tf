output "deployment" {
  value = {
    vpc_id               = module.platform.vpc_id
    private_subnet_ids   = module.platform.private_subnet_ids
    data_subnet_ids      = module.platform.data_subnet_ids
    eks_cluster_name     = module.platform.eks_cluster_name
    ecr_repository_url   = module.platform.ecr_repository_url
    evidence_bucket      = module.platform.evidence_bucket
    exports_bucket       = module.platform.exports_bucket
    database_secret_arn  = module.platform.database_secret_arn
    valkey_secret_arn    = module.platform.valkey_secret_arn
    platform_kms_key_arn = module.platform.platform_kms_key_arn
    audit_kms_key_arn    = module.platform.audit_kms_key_arn
    api_role_arns        = module.platform.api_role_arns
    worker_role_arns     = module.platform.worker_role_arns
  }
}
