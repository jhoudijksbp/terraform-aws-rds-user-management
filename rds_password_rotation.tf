module "rds_password_rotation_lambda" {
  count                    = "${var.deploy_password_rotation == true ? 1 : 0}"
  source                   = "app.terraform.io/ccv-group/rds-password-rotation/aws"
  kms_arns                 = [var.kms_key_id]
  vpc_id                   = var.vpc_id
  subnet_ids               = var.subnet_ids

  providers = {
    aws = aws
  }
}