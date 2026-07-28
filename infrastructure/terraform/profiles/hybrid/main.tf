resource "kubernetes_namespace_v1" "sip" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of"                  = "spatial-intelligence-platform"
      "pod-security.kubernetes.io/enforce"         = "restricted"
      "pod-security.kubernetes.io/enforce-version" = "latest"
      "pod-security.kubernetes.io/audit"           = "restricted"
      "pod-security.kubernetes.io/warn"            = "restricted"
    }
  }
}

resource "kubernetes_config_map_v1" "external_services" {
  metadata {
    name      = "sip-external-services"
    namespace = kubernetes_namespace_v1.sip.metadata[0].name
  }
  data = {
    SIP_DATABASE_HOST      = var.database_host
    SIP_VALKEY_HOST        = var.valkey_host
    SIP_EVIDENCE_BUCKET    = var.evidence_bucket
    SIP_OBJECT_STORE_REGION = var.object_store_region
    SIP_EXTERNAL_SECRETS_REQUIRED = "true"
  }
}

resource "kubernetes_network_policy_v1" "default_deny" {
  metadata {
    name      = "default-deny"
    namespace = kubernetes_namespace_v1.sip.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}
