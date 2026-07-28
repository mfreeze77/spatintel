variable "name" {
  description = "Short lowercase platform name used in resource names."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.name))
    error_message = "name must be 3-31 lowercase alphanumeric/hyphen characters and begin with a letter."
  }
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "region" {
  type = string
}

variable "kubernetes_namespace" {
  type        = string
  default     = "sip-system"
  description = "Namespace used by SIP workloads and EKS Pod Identity associations."
  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.kubernetes_namespace))
    error_message = "kubernetes_namespace must be a valid DNS label."
  }
}

variable "availability_zone_count" {
  type    = number
  default = 3
  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "Use two or three availability zones."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "public_access_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach the EKS public API when enabled. Never use 0.0.0.0/0 in production."
  default     = []
  validation {
    condition     = var.environment != "production" || !contains(var.public_access_cidrs, "0.0.0.0/0")
    error_message = "Production EKS API access may not allow 0.0.0.0/0."
  }
}

variable "enable_eks_public_endpoint" {
  type    = bool
  default = false
}

variable "platform_admin_principal_arns" {
  description = "Exact IAM role ARNs receiving EKS cluster-administrator access. Account root is rejected."
  type        = set(string)
  validation {
    condition = length(var.platform_admin_principal_arns) > 0 && alltrue([
      for arn in var.platform_admin_principal_arns :
      can(regex("^arn:[^:]+:iam::[0-9]{12}:role/.+$", arn))
    ])
    error_message = "Provide at least one IAM role ARN; users and account-root principals are not accepted."
  }
}

variable "kubernetes_version" {
  type    = string
  default = "1.34"
}

variable "eks_addon_versions" {
  description = "Exact EKS add-on versions resolved for the target region. Empty or placeholder values are rejected."
  type = object({
    vpc_cni                = string
    coredns                = string
    kube_proxy             = string
    eks_pod_identity_agent = string
  })
  validation {
    condition = alltrue([
      for value in values(var.eks_addon_versions) :
      length(trimspace(value)) > 0 && !startswith(value, "REPLACE_")
    ])
    error_message = "Every EKS add-on version must be pinned exactly and must not be a placeholder."
  }
}

variable "standard_instance_types" {
  type    = list(string)
  default = ["m7g.xlarge"]
}
variable "standard_min_size" {
  type    = number
  default = 3
}
variable "standard_desired_size" {
  type    = number
  default = 3
}
variable "standard_max_size" {
  type    = number
  default = 12
}
variable "enable_gpu_node_group" {
  type    = bool
  default = true
}
variable "gpu_instance_types" {
  type    = list(string)
  default = ["g6.2xlarge"]
}
variable "gpu_min_size" {
  type    = number
  default = 0
}
variable "gpu_desired_size" {
  type    = number
  default = 0
}
variable "gpu_max_size" {
  type    = number
  default = 4
}

variable "database_engine_version" {
  type    = string
  default = "18.4"
}
variable "database_instance_class" {
  type    = string
  default = "db.r7g.large"
}
variable "database_allocated_storage_gib" {
  type    = number
  default = 100
}
variable "database_max_allocated_storage_gib" {
  type    = number
  default = 2048
}
variable "database_backup_retention_days" {
  type    = number
  default = 35
}
variable "database_deletion_protection" {
  type    = bool
  default = true
}
variable "database_skip_final_snapshot" {
  type    = bool
  default = false
  validation {
    condition     = var.environment != "production" || !var.database_skip_final_snapshot
    error_message = "Production databases require a final snapshot."
  }
}

variable "valkey_engine_version" {
  type    = string
  default = "9.1"
}
variable "valkey_node_type" {
  type    = string
  default = "cache.r7g.large"
}
variable "valkey_replicas_per_node_group" {
  type    = number
  default = 2
}

variable "evidence_object_lock_days" {
  type    = number
  default = 30
}
variable "evidence_noncurrent_expiration_days" {
  type    = number
  default = 3650
}
variable "monthly_budget_usd" {
  type    = number
  default = 10000
}
variable "budget_notification_email" {
  type = string
}
variable "enable_guardduty" {
  type    = bool
  default = false
}
variable "enable_security_hub" {
  type    = bool
  default = false
}
variable "tags" {
  type    = map(string)
  default = {}
}
