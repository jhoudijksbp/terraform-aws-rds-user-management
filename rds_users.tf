locals {
  sql_users_map = flatten([
    for k, v in var.sql_users : {
      authentication         = try(v.authentication, "credentials")
      password               = try(v.password, "will_get_generated_later")
      privileges             = try(v.grants, "")
      rds_cluster_identifier = v.rds_cluster_identifier
      rds_endpoint           = v.rds_endpoint
      rds_port               = v.rds_port
      rotation               = try(v.rotation, false)
      master_user            = try(v.master_user, false)
      src_host               = try(v.src_host, "%")
      unique_name            = replace("${v.rds_cluster_identifier}_${k}","-","_")
      username               = try(v.username, k)
  }])
}

# Create a secret for the user
resource "aws_secretsmanager_secret" "db_user" {
  for_each   = { for user in local.sql_users_map : user.unique_name => user if user.master_user == false }
  name       = "db_user_${each.value.unique_name}"
  kms_key_id = var.kms_key_id
  tags       = merge(var.tags, { "SECRET_TYPE" = "RDS" })
}

# Create a separate user for the user privileges
resource "aws_secretsmanager_secret" "db_user_privs" {
  for_each   = { for user in local.sql_users_map : user.unique_name => user if user.master_user == false }
  name       = "db_user_privs_${each.value.unique_name}"
  kms_key_id = var.kms_key_id
  tags       = merge(var.tags, { "SECRET_TYPE" = "PRIVS_RDS" })
}

# Create a secret version for the user credentials
resource "aws_secretsmanager_secret_version" "db_user_secret_version" {
  for_each  = { for user in local.sql_users_map : user.unique_name => user if user.master_user == false }
  secret_id = aws_secretsmanager_secret.db_user[each.value.unique_name].id

  secret_string = jsonencode({
    authentication       = each.value.authentication,
    dbInstanceIdentifier = each.value.rds_cluster_identifier,
    engine               = "mysql",
    host                 = each.value.rds_endpoint,
    password             = each.value.password,
    port                 = each.value.rds_port,
    src_host             = each.value.src_host,
    username             = each.value.username
  })

  lifecycle {
    ignore_changes = [
      secret_string
    ]
  }
}

# Create a secret version for the user privileges
resource "aws_secretsmanager_secret_version" "db_user_privs_secret_version" {
  for_each  = { for user in local.sql_users_map : user.unique_name => user if user.master_user == false }
  secret_id = aws_secretsmanager_secret.db_user_privs[each.value.unique_name].id

  secret_string = jsonencode({
    authentication       = each.value.authentication,
    dbInstanceIdentifier = each.value.rds_cluster_identifier,
    engine               = "mysql",
    host                 = each.value.rds_endpoint,
    port                 = each.value.rds_port,
    privileges           = each.value.privileges,
    src_host             = each.value.src_host,
    username             = each.value.username
  })
}

# Enable password rotation for secrets which are configured for password rotation
resource "aws_secretsmanager_secret_rotation" "db_user_secret_rotation" {
  for_each            = { for user in local.sql_users_map : user.unique_name => user if user.rotation && user.master_user == false && var.deploy_password_rotation }
  secret_id           = aws_secretsmanager_secret.db_user[each.value.unique_name].id
  rotation_lambda_arn = module.rds_password_rotation[0].arn

  rotation_rules {
    automatically_after_days = 30
  }
}

# Create a secret for Master users
resource "aws_secretsmanager_secret" "db_master_user" {
  for_each   = { for user in local.sql_users_map : user.unique_name => user if user.master_user }
  name       = "db_master_user_${each.value.unique_name}"
  kms_key_id = var.kms_key_id
  tags       = merge(var.tags, { "SECRET_TYPE" = "MASTER_RDS", "CL_IDENTIFIER" = "${each.value.rds_cluster_identifier}" })
}

# Create a secret version for Master users 
resource "aws_secretsmanager_secret_version" "db_master_user_secret_version" {
  for_each  = { for user in local.sql_users_map : user.unique_name => user if user.master_user }
  secret_id = aws_secretsmanager_secret.db_master_user[each.value.unique_name].id

  secret_string = jsonencode({
    authentication       = each.value.authentication,
    dbInstanceIdentifier = each.value.rds_cluster_identifier,
    engine               = "mysql",
    host                 = each.value.rds_endpoint,
    password             = each.value.password,
    port                 = each.value.rds_port,
    src_host             = each.value.src_host,
    username             = each.value.username
  })

  lifecycle {
    ignore_changes = [
      secret_string
    ]
  }
}

# Enable password rotation for master users
resource "aws_secretsmanager_secret_rotation" "db_master_user_secret_rotation" {
  for_each            = { for user in local.sql_users_map : user.unique_name => user if user.rotation && user.master_user && var.deploy_password_rotation }
  secret_id           = aws_secretsmanager_secret.db_master_user[each.value.unique_name].id
  rotation_lambda_arn = module.rds_password_rotation[0].arn

  rotation_rules {
    automatically_after_days = 30
  }
}
