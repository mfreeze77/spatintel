resource "aws_iam_role" "eks_cluster" {
  name = "${local.prefix}-eks-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}
resource "aws_iam_role_policy_attachment" "eks_cluster" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${local.prefix}/cluster"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.audit.arn
  tags              = local.tags
}
resource "aws_eks_cluster" "this" {
  name                      = local.prefix
  role_arn                  = aws_iam_role.eks_cluster.arn
  version                   = var.kubernetes_version
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = false
  }
  encryption_config {
    provider {
      key_arn = aws_kms_key.platform.arn
    }
    resources = ["secrets"]
  }
  vpc_config {
    endpoint_private_access = true
    endpoint_public_access  = var.enable_eks_public_endpoint
    public_access_cidrs     = var.enable_eks_public_endpoint ? var.public_access_cidrs : []
    subnet_ids              = concat(aws_subnet.private[*].id, aws_subnet.public[*].id)
  }
  tags       = local.tags
  depends_on = [aws_iam_role_policy_attachment.eks_cluster, aws_cloudwatch_log_group.eks]
}

resource "aws_iam_role" "eks_nodes" {
  name = "${local.prefix}-eks-nodes"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}
resource "aws_iam_role_policy_attachment" "eks_nodes_worker" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}
resource "aws_iam_role_policy_attachment" "eks_nodes_ecr" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly"
}
resource "aws_iam_role_policy_attachment" "eks_nodes_cni" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_launch_template" "standard" {
  name_prefix            = "${local.prefix}-standard-"
  update_default_version = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      encrypted             = true
      volume_size           = 100
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }
  monitoring {
    enabled = true
  }
  tag_specifications {
    resource_type = "instance"
    tags          = local.tags
  }
  tags = local.tags
}

resource "aws_launch_template" "gpu" {
  count                  = var.enable_gpu_node_group ? 1 : 0
  name_prefix            = "${local.prefix}-gpu-"
  update_default_version = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      encrypted             = true
      volume_size           = 250
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }
  monitoring {
    enabled = true
  }
  tag_specifications {
    resource_type = "instance"
    tags          = local.tags
  }
  tags = local.tags
}

resource "aws_eks_node_group" "standard" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "standard"
  node_role_arn   = aws_iam_role.eks_nodes.arn
  subnet_ids      = aws_subnet.private[*].id
  instance_types  = var.standard_instance_types
  capacity_type   = "ON_DEMAND"
  ami_type        = "AL2023_ARM_64_STANDARD"
  version         = var.kubernetes_version
  launch_template {
    id      = aws_launch_template.standard.id
    version = aws_launch_template.standard.latest_version
  }
  scaling_config {
    min_size     = var.standard_min_size
    desired_size = var.standard_desired_size
    max_size     = var.standard_max_size
  }
  update_config {
    max_unavailable_percentage = 25
  }
  labels = {
    "sip.open/worker-class" = "standard"
  }
  tags = local.tags
  depends_on = [
    aws_iam_role_policy_attachment.eks_nodes_worker,
    aws_iam_role_policy_attachment.eks_nodes_ecr,
    aws_iam_role_policy_attachment.eks_nodes_cni,
  ]
}

resource "aws_eks_node_group" "gpu" {
  count           = var.enable_gpu_node_group ? 1 : 0
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "gpu"
  node_role_arn   = aws_iam_role.eks_nodes.arn
  subnet_ids      = aws_subnet.private[*].id
  instance_types  = var.gpu_instance_types
  capacity_type   = "ON_DEMAND"
  ami_type        = "AL2023_x86_64_NVIDIA"
  version         = var.kubernetes_version
  launch_template {
    id      = aws_launch_template.gpu[0].id
    version = aws_launch_template.gpu[0].latest_version
  }
  scaling_config {
    min_size     = var.gpu_min_size
    desired_size = var.gpu_desired_size
    max_size     = var.gpu_max_size
  }
  update_config {
    max_unavailable = 1
  }
  labels = {
    "sip.open/worker-class" = "gpu"
  }
  taint {
    key    = "sip.open/gpu"
    value  = "true"
    effect = "NO_SCHEDULE"
  }
  tags = local.tags
  depends_on = [
    aws_iam_role_policy_attachment.eks_nodes_worker,
    aws_iam_role_policy_attachment.eks_nodes_ecr,
    aws_iam_role_policy_attachment.eks_nodes_cni,
  ]
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "vpc-cni"
  addon_version               = var.eks_addon_versions.vpc_cni
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "PRESERVE"
  tags                        = local.tags
}
resource "aws_eks_addon" "coredns" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "coredns"
  addon_version               = var.eks_addon_versions.coredns
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "PRESERVE"
  tags                        = local.tags
}
resource "aws_eks_addon" "kube_proxy" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "kube-proxy"
  addon_version               = var.eks_addon_versions.kube_proxy
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "PRESERVE"
  tags                        = local.tags
}
resource "aws_eks_addon" "pod_identity" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "eks-pod-identity-agent"
  addon_version               = var.eks_addon_versions.eks_pod_identity_agent
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "PRESERVE"
  tags                        = local.tags
}

resource "aws_eks_access_entry" "platform_admin" {
  for_each      = var.platform_admin_principal_arns
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
  type          = "STANDARD"
  tags          = local.tags
}
resource "aws_eks_access_policy_association" "platform_admin" {
  for_each      = var.platform_admin_principal_arns
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = aws_eks_access_entry.platform_admin[each.value].principal_arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope {
    type = "cluster"
  }
}
