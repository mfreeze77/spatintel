output "namespace" {
  value = kubernetes_namespace_v1.sip.metadata[0].name
}
output "external_secret_requirements" {
  value = [
    "database credentials",
    "Valkey auth token",
    "object-store workload identity",
    "SIP envelope master key reference",
    "audit-chain key reference",
  ]
}
