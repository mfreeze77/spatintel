resource "terraform_data" "local_profile" {
  input = {
    profile              = "local"
    compose_project_name = var.compose_project_name
    data_root            = var.data_root
    command              = "docker compose -f infrastructure/compose/docker-compose.yml up --build"
    warning              = "The optional MinIO service is development-only and denied in release profiles."
  }
  lifecycle {
    precondition {
      condition     = !startswith(var.data_root, "/etc") && !startswith(var.data_root, "/usr")
      error_message = "data_root must not point into a system configuration or binary directory."
    }
  }
}
