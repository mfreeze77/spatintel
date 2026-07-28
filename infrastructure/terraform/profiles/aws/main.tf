module "platform" {
  source                                = "../../modules/aws-platform"

  name                                  = var.name
  environment                           = var.environment
  region                                = var.region
  kubernetes_namespace                  = var.kubernetes_namespace
  budget_notification_email             = var.budget_notification_email
  platform_admin_principal_arns         = var.platform_admin_principal_arns
  public_access_cidrs                   = var.public_access_cidrs
  enable_eks_public_endpoint            = length(var.public_access_cidrs) > 0
  eks_addon_versions                    = var.eks_addon_versions
  monthly_budget_usd                    = var.monthly_budget_usd
  enable_guardduty                      = var.enable_guardduty
  enable_security_hub                   = var.enable_security_hub
}
