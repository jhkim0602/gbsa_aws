terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

variable "name" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "availability_zone_count" {
  type    = number
  default = 2
}

variable "enable_nat_gateway" {
  type    = bool
  default = true
}

variable "nat_gateway_per_az" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_region" "current" {}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

locals {
  availability_zones = slice(
    data.aws_availability_zones.available.names,
    0,
    var.availability_zone_count
  )
  interface_endpoints = toset([
    "ecr.api",
    "ecr.dkr",
    "logs",
    "secretsmanager",
    "sqs",
    "states",
    "sts",
    "xray",
  ])
  tags = merge(var.tags, {
    Component = "network"
  })
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, { Name = "${var.name}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name}-igw" })
}

resource "aws_subnet" "public" {
  count = var.availability_zone_count

  vpc_id                  = aws_vpc.this.id
  availability_zone       = local.availability_zones[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  map_public_ip_on_launch = false

  tags = merge(local.tags, {
    Name = "${var.name}-public-${count.index + 1}"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  count = var.availability_zone_count

  vpc_id            = aws_vpc.this.id
  availability_zone = local.availability_zones[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)

  tags = merge(local.tags, {
    Name = "${var.name}-private-${count.index + 1}"
    Tier = "private"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name}-public" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count = var.availability_zone_count

  route_table_id = aws_route_table.public.id
  subnet_id      = aws_subnet.public[count.index].id
}

resource "aws_eip" "nat" {
  count = var.enable_nat_gateway ? (
    var.nat_gateway_per_az ? var.availability_zone_count : 1
  ) : 0

  domain = "vpc"
  tags = merge(local.tags, {
    Name = "${var.name}-nat-${count.index + 1}"
  })

  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  count = var.enable_nat_gateway ? (
    var.nat_gateway_per_az ? var.availability_zone_count : 1
  ) : 0

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags = merge(local.tags, {
    Name = "${var.name}-nat-${count.index + 1}"
  })
}

resource "aws_route_table" "private" {
  count  = var.availability_zone_count
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name}-private-${count.index + 1}" })
}

resource "aws_route" "private_internet" {
  count = var.enable_nat_gateway ? var.availability_zone_count : 0

  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id = aws_nat_gateway.this[
    var.nat_gateway_per_az ? count.index : 0
  ].id
}

resource "aws_route_table_association" "private" {
  count = var.availability_zone_count

  route_table_id = aws_route_table.private[count.index].id
  subnet_id      = aws_subnet.private[count.index].id
}

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "CloudFront origin traffic only"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_cloudfront" {
  security_group_id = aws_security_group.alb.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
}

resource "aws_security_group" "application" {
  name        = "${var.name}-application"
  description = "ECS application tasks"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "application_from_alb" {
  security_group_id            = aws_security_group.application.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "application" {
  security_group_id = aws_security_group.application.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "database" {
  name        = "${var.name}-database"
  description = "Aurora access from application tasks"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "database_from_application" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.application.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "endpoints" {
  name        = "${var.name}-endpoints"
  description = "Private interface endpoints"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_application" {
  security_group_id            = aws_security_group.endpoints.id
  referenced_security_group_id = aws_security_group.application.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoints

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  tags                = merge(local.tags, { Name = "${var.name}-${each.value}" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id
  tags              = local.tags
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id
  tags              = local.tags
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "application_security_group_id" {
  value = aws_security_group.application.id
}

output "database_security_group_id" {
  value = aws_security_group.database.id
}

output "endpoint_security_group_id" {
  value = aws_security_group.endpoints.id
}
