locals {
  prefix = "${var.name}-${var.environment}"
  tags = merge(var.tags, {
    Application        = "Spatial Intelligence Platform"
    Environment        = var.environment
    ManagedBy          = "Terraform"
    DataClassification = "mixed"
  })
  azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)
  api_service_accounts = toset([
    "control-api",
    "identity-policy",
    "capture-service",
    "workflow-service",
    "scene-service",
    "evidence-service",
    "search-service",
    "export-service",
    "notification-service",
    "audit-service",
    "security-ops",
    "representation-api",
    "provider-registry",
    "representation-publisher",
  ])
  worker_service_accounts = toset([
    "worker-capture-normalizer",
    "worker-change-detection",
    "worker-collision-navigation",
    "worker-depth-normalizer",
    "worker-document-media",
    "worker-fusion-tsdf",
    "worker-geometry-cleanup",
    "worker-lingbot-adapter",
    "worker-mesh-lod",
    "worker-pose-optimizer",
    "worker-report-export",
    "worker-representation-quality",
    "worker-semantics",
    "worker-splat",
    "worker-splat-normalizer",
    "worker-splat-surface",
  ])
  migration_service_accounts = toset(["sip-migrator"])
}
