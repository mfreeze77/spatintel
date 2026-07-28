data "aws_iam_policy_document" "pod_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole", "sts:TagSession"]
  }
}

resource "aws_iam_role" "api" {
  for_each           = local.api_service_accounts
  name               = "${local.prefix}-${each.value}"
  assume_role_policy = data.aws_iam_policy_document.pod_assume.json
  tags               = local.tags
}
resource "aws_iam_role" "worker" {
  for_each           = local.worker_service_accounts
  name               = "${local.prefix}-${each.value}"
  assume_role_policy = data.aws_iam_policy_document.pod_assume.json
  tags               = local.tags
}
resource "aws_iam_role" "migrator" {
  for_each           = local.migration_service_accounts
  name               = "${local.prefix}-${each.value}"
  assume_role_policy = data.aws_iam_policy_document.pod_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "asset_access" {
  statement {
    sid = "AssetObjects"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = [
      "${aws_s3_bucket.evidence.arn}/tenants/*",
      "${aws_s3_bucket.exports.arn}/tenants/*",
    ]
  }
  statement {
    sid = "ListScopedPrefixes"
    actions = [
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
    ]
    resources = [aws_s3_bucket.evidence.arn, aws_s3_bucket.exports.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["tenants/*"]
    }
  }
  statement {
    sid = "EnvelopeKeys"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:ReEncrypt*",
    ]
    resources = [aws_kms_key.platform.arn, aws_kms_key.audit.arn]
  }
}
resource "aws_iam_policy" "asset_access" {
  name   = "${local.prefix}-asset-access"
  policy = data.aws_iam_policy_document.asset_access.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "api_asset" {
  for_each   = toset(["capture-service", "evidence-service", "export-service", "representation-publisher"])
  role       = aws_iam_role.api[each.value].name
  policy_arn = aws_iam_policy.asset_access.arn
}
resource "aws_iam_role_policy_attachment" "worker_asset" {
  for_each   = local.worker_service_accounts
  role       = aws_iam_role.worker[each.value].name
  policy_arn = aws_iam_policy.asset_access.arn
}

data "aws_iam_policy_document" "secret_read" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_db_instance.this.master_user_secret[0].secret_arn,
      aws_secretsmanager_secret.valkey.arn,
    ]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.platform.arn]
  }
}
resource "aws_iam_policy" "secret_read" {
  name   = "${local.prefix}-secret-read"
  policy = data.aws_iam_policy_document.secret_read.json
  tags   = local.tags
}
resource "aws_iam_role_policy_attachment" "api_secrets" {
  for_each   = local.api_service_accounts
  role       = aws_iam_role.api[each.value].name
  policy_arn = aws_iam_policy.secret_read.arn
}
resource "aws_iam_role_policy_attachment" "worker_secrets" {
  for_each   = local.worker_service_accounts
  role       = aws_iam_role.worker[each.value].name
  policy_arn = aws_iam_policy.secret_read.arn
}
resource "aws_iam_role_policy_attachment" "migrator_secrets" {
  for_each   = local.migration_service_accounts
  role       = aws_iam_role.migrator[each.value].name
  policy_arn = aws_iam_policy.secret_read.arn
}

resource "aws_eks_pod_identity_association" "api" {
  for_each        = local.api_service_accounts
  cluster_name    = aws_eks_cluster.this.name
  namespace       = var.kubernetes_namespace
  service_account = each.value
  role_arn        = aws_iam_role.api[each.value].arn
  tags            = local.tags
}
resource "aws_eks_pod_identity_association" "worker" {
  for_each        = local.worker_service_accounts
  cluster_name    = aws_eks_cluster.this.name
  namespace       = var.kubernetes_namespace
  service_account = each.value
  role_arn        = aws_iam_role.worker[each.value].arn
  tags            = local.tags
}

resource "aws_eks_pod_identity_association" "migrator" {
  for_each        = local.migration_service_accounts
  cluster_name    = aws_eks_cluster.this.name
  namespace       = var.kubernetes_namespace
  service_account = each.value
  role_arn        = aws_iam_role.migrator[each.value].arn
  tags            = local.tags
}
