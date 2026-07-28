variable "name" {
  type    = string
  default = "sip"
}
variable "environment" {
  type    = string
  default = "production"
}
variable "region" {
  type    = string
  default = "us-east-2"
}
variable "kubernetes_namespace" {
  type    = string
  default = "sip-system"
}
variable "platform_admin_principal_arns" {
  type        = set(string)
  description = "Explicit IAM role ARNs for EKS platform administrators."
}
variable "budget_notification_email" {
  type        = string
  description = "Operational email for forecast and actual cost-budget alerts."
}
variable "public_access_cidrs" {
  type        = list(string)
  default     = []
  description = "Explicit trusted CIDRs; keep empty with a private-only EKS API."
}
variable "eks_addon_versions" {
  type = object({
    vpc_cni                = string
    coredns                = string
    kube_proxy             = string
    eks_pod_identity_agent = string
  })
}
variable "monthly_budget_usd" {
  type    = number
  default = 10000
}
variable "enable_guardduty" {
  type    = bool
  default = false
}
variable "enable_security_hub" {
  type    = bool
  default = false
}
