resource "aws_ecr_repository" "application" {
  name                 = "${local.prefix}/application"
  image_tag_mutability = "IMMUTABLE"
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.platform.arn
  }
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.tags
}
resource "aws_ecr_lifecycle_policy" "application" {
  repository = aws_ecr_repository.application.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "expire untagged"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "retain 100 release images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 100
        }
        action = { type = "expire" }
      },
    ]
  })
}
