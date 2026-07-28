variable "kubeconfig_path" {
  type        = string
  description = "Path to a restricted operator kubeconfig; never commit the file."
}
variable "kubeconfig_context" {
  type        = string
  description = "Exact context for the target cluster."
}
variable "namespace" {
  type    = string
  default = "sip-system"
}
variable "database_host" {
  type        = string
  description = "Private PostgreSQL endpoint. Credentials are injected out of band by a secret manager."
}
variable "valkey_host" {
  type        = string
  description = "Private TLS Valkey endpoint. Credentials are injected out of band by a secret manager."
}
variable "evidence_bucket" {
  type        = string
  description = "Approved S3-compatible content-addressed evidence bucket."
}
variable "object_store_region" {
  type        = string
  description = "Data residency region recorded in policy and provider manifests."
}
