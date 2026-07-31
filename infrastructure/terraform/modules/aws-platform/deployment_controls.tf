locals {
  deployment_dead_letter_queue_name = "${local.prefix}-deployment-dlq"
  deployment_work_queue_name        = "${local.prefix}-deployment-work"
  deployment_tenant_quota_policy = {
    enforced_by = "deployment-control"
    scope       = "tenant-and-project"
  }
  deployment_global_budget_guardrail = {
    enforced_by = "operations-intelligence"
    fail_closed = true
  }
  provider_replacement_paths = {
    database     = "open-sql-export"
    object_store = "s3-compatible-preservation-export"
    queue        = "versioned-event-replay"
    workflow     = "sip-operation-manifest"
    kms          = "envelope-key-rewrap"
    secrets      = "external-secret-reference-rotation"
    cdn          = "signed-redacted-derivative-export"
    gpu          = "compute-profile-adapter"
  }
}

resource "aws_sqs_queue" "deployment_dead_letter" {
  name                              = local.deployment_dead_letter_queue_name
  kms_master_key_id                 = aws_kms_key.platform.arn
  message_retention_seconds         = 1209600
  sqs_managed_sse_enabled           = false
  visibility_timeout_seconds        = 300
  tags                              = merge(local.tags, { Purpose = "deployment-dead-letter" })
}

resource "aws_sqs_queue" "deployment_work" {
  name                       = local.deployment_work_queue_name
  kms_master_key_id          = aws_kms_key.platform.arn
  visibility_timeout_seconds = 900
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.deployment_dead_letter.arn
    maxReceiveCount     = 3
  })
  tags = merge(local.tags, {
    Purpose          = "deployment-work"
    TenantQuota      = "enforced"
    GlobalBudget     = "enforced"
    RestrictedEgress = "true"
  })
}

output "deployment_control_posture" {
  value = {
    dead_letter_queue_arn       = aws_sqs_queue.deployment_dead_letter.arn
    work_queue_arn              = aws_sqs_queue.deployment_work.arn
    tenant_quota_policy         = local.deployment_tenant_quota_policy
    global_budget_guardrail     = local.deployment_global_budget_guardrail
    provider_replacement_paths  = local.provider_replacement_paths
  }
}
