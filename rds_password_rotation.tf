module "rds_password_rotation" {
  count                 = "${var.deploy_password_rotation == true ? 1 : 0}"
  create_kms_iam_policy = var.create_kms_iam_policy
  source                = "app.terraform.io/ccv-group/rds-password-rotation/aws"
  kms_arns              = [var.kms_key_id]
  vpc_id                = var.vpc_id
  subnet_ids            = var.subnet_ids

  providers = {
    aws = aws
  }
}
