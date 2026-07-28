data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${local.prefix}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.prefix}-igw" })
}

resource "aws_subnet" "public" {
  count                   = var.availability_zone_count
  vpc_id                  = aws_vpc.this.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  map_public_ip_on_launch = false
  tags = merge(local.tags, {
    Name                     = "${local.prefix}-public-${local.azs[count.index]}"
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_subnet" "private" {
  count             = var.availability_zone_count
  vpc_id            = aws_vpc.this.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  tags = merge(local.tags, {
    Name                              = "${local.prefix}-private-${local.azs[count.index]}"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

resource "aws_subnet" "data" {
  count             = var.availability_zone_count
  vpc_id            = aws_vpc.this.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  tags               = merge(local.tags, { Name = "${local.prefix}-data-${local.azs[count.index]}" })
}

resource "aws_eip" "nat" {
  count      = var.availability_zone_count
  domain     = "vpc"
  tags       = merge(local.tags, { Name = "${local.prefix}-nat-${local.azs[count.index]}" })
  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  count         = var.availability_zone_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = merge(local.tags, { Name = "${local.prefix}-nat-${local.azs[count.index]}" })
  depends_on    = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(local.tags, { Name = "${local.prefix}-public" })
}

resource "aws_route_table_association" "public" {
  count          = var.availability_zone_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count  = var.availability_zone_count
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[count.index].id
  }
  tags = merge(local.tags, { Name = "${local.prefix}-private-${local.azs[count.index]}" })
}

resource "aws_route_table_association" "private" {
  count          = var.availability_zone_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table" "data" {
  count  = var.availability_zone_count
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.prefix}-data-${local.azs[count.index]}" })
}

resource "aws_route_table_association" "data" {
  count          = var.availability_zone_count
  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data[count.index].id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(aws_route_table.private[*].id, aws_route_table.data[*].id)
  tags              = merge(local.tags, { Name = "${local.prefix}-s3-endpoint" })
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${local.prefix}-endpoints-"
  description = "HTTPS from private SIP networks to AWS interface endpoints"
  vpc_id      = aws_vpc.this.id
  ingress {
    description = "HTTPS from VPC"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_vpc_endpoint" "interfaces" {
  for_each            = toset(["ecr.api", "ecr.dkr", "logs", "kms", "secretsmanager", "sts"])
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${var.region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.prefix}-${replace(each.value, ".", "-")}-endpoint" })
}

resource "aws_cloudwatch_log_group" "vpc_flow" {
  name              = "/sip/${local.prefix}/vpc-flow"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.audit.arn
  tags              = local.tags
}

resource "aws_iam_role" "vpc_flow" {
  name = "${local.prefix}-vpc-flow"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "vpc_flow" {
  role = aws_iam_role.vpc_flow.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Resource = "${aws_cloudwatch_log_group.vpc_flow.arn}:*"
    }]
  })
}

resource "aws_flow_log" "this" {
  iam_role_arn             = aws_iam_role.vpc_flow.arn
  log_destination          = aws_cloudwatch_log_group.vpc_flow.arn
  log_destination_type     = "cloud-watch-logs"
  traffic_type             = "ALL"
  vpc_id                   = aws_vpc.this.id
  max_aggregation_interval = 60
  tags                     = local.tags
}
