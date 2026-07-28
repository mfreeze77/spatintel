provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Application = "Spatial Intelligence Platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
