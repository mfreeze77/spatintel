provider "aws" {
  region = var.region
}
resource "random_id" "suffix" {
  byte_length = 4
}
resource "aws_kms_key" "state" {
  description             = "SIP Terraform state encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
resource "aws_kms_alias" "state" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.state.key_id
}
resource "aws_s3_bucket" "state" {
  bucket = "${var.name}-${random_id.suffix.hex}"
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.state.arn
      sse_algorithm     = "aws:kms"
    }
  }
}
data "aws_iam_policy_document" "state" {
  statement {
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state.json
}
