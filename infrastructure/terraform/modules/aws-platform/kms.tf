data "aws_iam_policy_document" "kms_platform" {
  statement {
    sid    = "AccountAdministration"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }
}

resource "aws_kms_key" "platform" {
  description             = "SIP platform envelope and service encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  multi_region            = true
  policy                  = data.aws_iam_policy_document.kms_platform.json
  tags                    = local.tags
}
resource "aws_kms_alias" "platform" {
  name          = "alias/${local.prefix}-platform"
  target_key_id = aws_kms_key.platform.key_id
}

data "aws_iam_policy_document" "kms_audit" {
  statement {
    sid    = "AccountAdministration"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }
  statement {
    sid    = "CloudTrailEncryption"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["kms:GenerateDataKey*", "kms:DescribeKey"]
    resources = ["*"]
    condition {
      test     = "StringLike"
      variable = "kms:EncryptionContext:aws:cloudtrail:arn"
      values   = ["arn:${data.aws_partition.current.partition}:cloudtrail:*:${data.aws_caller_identity.current.account_id}:trail/*"]
    }
  }
  statement {
    sid    = "CloudWatchLogsEncryption"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["logs.${var.region}.amazonaws.com"]
    }
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Describe*",
    ]
    resources = ["*"]
    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:*" ]
    }
  }
}

resource "aws_kms_key" "audit" {
  description             = "SIP immutable audit, logs, and evidence encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  multi_region            = true
  policy                  = data.aws_iam_policy_document.kms_audit.json
  tags                    = local.tags
}
resource "aws_kms_alias" "audit" {
  name          = "alias/${local.prefix}-audit"
  target_key_id = aws_kms_key.audit.key_id
}
