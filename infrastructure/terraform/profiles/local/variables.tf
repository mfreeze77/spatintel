variable "compose_project_name" {
  type    = string
  default = "sip"
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9_-]+$", var.compose_project_name))
    error_message = "compose_project_name must be a valid Compose project name."
  }
}
variable "data_root" {
  type    = string
  default = "./runtime"
}
