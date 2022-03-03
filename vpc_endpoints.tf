resource "aws_security_group" "vpc_endpoint_secrets_manager_sg" {
  count       = "${var.create_vpc_secm_endpoint == true ? 1 : 0}"

  name        = "vpc_endpoint_secrets_manager_sg"
  description = "Allow traffic from Lambda in private subnets to secrets manager"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group_rule" "vpc_endpoint_secrets_manager_sg_rule" {
  count                    = "${var.create_vpc_secm_endpoint == true ? 1 : 0}"

  description              = "Allow Ingress traffic over port 443 to this endpoint"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.vpc_endpoint_secrets_manager_sg[0].id
  source_security_group_id = module.rds_user_management_lambda.security_group_id
  type                     = "ingress"
  to_port                  = 443
}

resource "aws_security_group_rule" "vpc_endpoint_secrets_manager_sg_rule" {
  count                    = "${var.create_vpc_secm_endpoint == true && deploy_password_rotation == true ? 1 : 0}"

  description              = "Allow Ingress traffic over port 443 to this endpoint"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.vpc_endpoint_secrets_manager_sg[0].id
  source_security_group_id = module.rds_password_rotation.security_group_id
  type                     = "ingress"
  to_port                  = 443
}

resource "aws_vpc_endpoint" "vpc_endpoint_secrets_manager" {
  count               = "${var.create_vpc_secm_endpoint == true ? 1 : 0}"

  private_dns_enabled = true
  service_name        = "com.amazonaws.eu-west-1.secretsmanager"
  subnet_ids          =  var.subnet_ids
  vpc_endpoint_type   = "Interface"
  vpc_id              = var.vpc_id
  tags = var.tags

  security_group_ids = [
    aws_security_group.vpc_endpoint_secrets_manager_sg[0].id,
  ]
}

resource "aws_security_group" "vpc_endpoint_rds_sg" {
  count       = "${var.create_vpc_rds_endpoint == true ? 1 : 0}"

  name        = "vpc_endpoint_rds_sg"
  description = "Allow traffic from Lambda in private subnets to RDS"
  vpc_id      = var.vpc_id

  tags = var.tags
}

resource "aws_security_group_rule" "vpc_endpoint_rds_sg_rule" {
  count                    = "${var.create_vpc_rds_endpoint == true ? 1 : 0}"

  description              = "Allow Ingress traffic over port 443 to this endpoint"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.vpc_endpoint_rds_sg[0].id
  source_security_group_id = module.rds_user_management_lambda.security_group_id
  to_port                  = 443
  type                     = "ingress"
}

resource "aws_vpc_endpoint" "vpc_endpoint_rds" {
  count               = "${var.create_vpc_rds_endpoint == true ? 1 : 0}"

  private_dns_enabled = true
  service_name        = "com.amazonaws.eu-west-1.rds"
  subnet_ids          =  var.subnet_ids
  vpc_endpoint_type   = "Interface"
  vpc_id              = var.vpc_id
  tags = var.tags

  security_group_ids = [
    aws_security_group.vpc_endpoint_rds_sg[0].id,
  ]
}

resource "aws_security_group" "vpc_endpoint_rds_data_sg" {
  count       = "${var.create_vpc_rds_endpoint == true ? 1 : 0}"

  name        = "vpc_endpoint_rds_data_sg"
  description = "Allow traffic from Lambda in private subnets to RDS Data API"
  vpc_id      = var.vpc_id
  tags = var.tags
}

resource "aws_security_group_rule" "vpc_endpoint_rds_data_sg_rule" {
  count                    = "${var.create_vpc_rds_endpoint == true ? 1 : 0}"

  description              = "Allow Ingress traffic over port 443 to this endpoint"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.vpc_endpoint_rds_data_sg[0].id
  source_security_group_id = module.rds_user_management_lambda.security_group_id
  to_port                  = 443
  type                     = "ingress"
}

resource "aws_vpc_endpoint" "vpc_endpoint_rds_data" {
  count               = "${var.create_vpc_rds_endpoint == true ? 1 : 0}"

  private_dns_enabled = true
  service_name        = "com.amazonaws.eu-west-1.rds-data"
  subnet_ids          =  var.subnet_ids
  vpc_endpoint_type   = "Interface"
  vpc_id              = var.vpc_id
  tags = var.tags

  security_group_ids = [
    aws_security_group.vpc_endpoint_rds_data_sg[0].id,
  ]
}
