locals {
  sql_users_map = flatten([
    for k, v in var.sql_users : {
      authentication         = v.authentication
      privileges             = v.grants
      rds_cluster_identifier = v.rds_cluster_identifier
      rds_endpoint           = v.rds_endpoint
      rds_port               = v.rds_port
      rotation               = try(v.rotation, false)
      src_host               = v.src_host
      username               = k
  }])
}

resource "aws_secretsmanager_secret" "db_user" {
  for_each   = var.sql_users
  name       = "db_user_${each.key}"
  kms_key_id = var.kms_key_id
  tags       = merge(var.tags, { "SECRET_TYPE" = "RDS" })
}

resource "aws_secretsmanager_secret_version" "db_user_secret_version" {
  for_each  = { for user in local.sql_users_map : user.username => user }
  secret_id = aws_secretsmanager_secret.db_user[each.value.username].id

  secret_string = jsonencode({
    authentication       = each.value.authentication,
    dbInstanceIdentifier = each.value.rds_cluster_identifier,
    engine               = "mysql",
    host                 = each.value.rds_endpoint,
    password             = "will_get_generated_later",
    port                 = each.value.rds_port,
    privileges           = each.value.privileges,
    src_host             = each.value.src_host,
    username             = each.value.username
  })

  lifecycle {
    ignore_changes = [
      secret_string
    ]
  }
}

#resource "aws_secretsmanager_secret_rotation" "db_user_secret_rotation" {
#  for_each            = { for user in local.sql_users_map : user.username => user if user.rotation }
#  secret_id           = aws_secretsmanager_secret.db_user[each.value.username].id
#  rotation_lambda_arn = module.rds_password_rotation_lambda.arn
#
#  rotation_rules {
#    automatically_after_days = 30
#  }
#}
