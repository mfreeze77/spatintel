output "state_bucket" {
  value = aws_s3_bucket.state.id
}
output "state_kms_key_arn" {
  value = aws_kms_key.state.arn
}
