locals {
  sql_users_map = flatten([
    for k, v in var.sql_users : {
      authentication         = v.authentication
      privileges             = v.grants
      rds_cluster_identifier = v.rds_cluster_identifier
      rds_endpoint           = v.rds_endpoint
      rds_port               = v.rds_port
      rotation               = try(v.rotation, false)
      master_user            = try(v.master_user, false)
      src_host               = v.src_host
      username               = k
  }])
}

# Create a secret for the user
resource "aws_secretsmanager_secret" "db_user" {
  for_each   = { for user in local.sql_users_map : "${user.rds_cluster_identifier}_${user.username}" => user if user.master_user == false }
  name       = "db_user_${each.value.rds_cluster_identifier}_${each.value.username}"
  kms_key_id = var.kms_key_id
  tags       = merge(var.tags, { "SECRET_TYPE" = "RDS" })
}

# Create a separate user for the user privileges
resource "aws_secretsmanager_secret" "db_user_privs" {
  for_each   = var.sql_users
  name       = "db_user_privs_${each.value.rds_cluster_identifier}_${each.value.username}"
  kms_key_id = var.kms_key_id
  tags       = merge(var.tags, { "SECRET_TYPE" = "PRIVS_RDS" })
}

# Create a secret version for the user credentials
resource "aws_secretsmanager_secret_version" "db_user_secret_version" {
  for_each  = { for user in local.sql_users_map : user.username => user }
  secret_id = aws_secretsmanager_secret.db_user[{"${user.rds_cluster_identifier}_${user.username}"}].id

  secret_string = jsonencode({
    authentication       = each.value.authentication,
    dbInstanceIdentifier = each.value.rds_cluster_identifier,
    engine               = "mysql",
    host                 = each.value.rds_endpoint,
    password             = "will_get_generated_later",
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
  for_each  = { for user in local.sql_users_map : user.username => user }
  secret_id = aws_secretsmanager_secret.db_user_privs[{"${user.rds_cluster_identifier}_${user.username}"}].id

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
  for_each            = { for user in local.sql_users_map : user.username => user if user.rotation && var.deploy_password_rotation }
  secret_id           = aws_secretsmanager_secret.db_user[{"${user.rds_cluster_identifier}_${user.username}"}].id
  rotation_lambda_arn = module.rds_password_rotation[0].arn

  rotation_rules {
    automatically_after_days = 30
  }
}

# Execute the usermanagement Lamba
resource "aws_cloudformation_stack" "execute_lambda_user_management" {
    name               = "rds-user-management-lambda"
    timeout_in_minutes = 5
    tags               = var.tags
  
    template_body = <<EOF
  {
    "Description" : "Execute a Lambda and return the results",
    "Resources": {
      "ExecuteLambda": {
        "Type": "Custom::ExecuteLambda",
        "Properties": 
          ${jsonencode(
    merge(
      {
        "ServiceToken" = module.rds_user_management_lambda.arn
      },
      {
        "run_on_every_apply" = "${timestamp()}"
      },
    ),
    )}
      }
    },
    "Outputs": {
      ${join(
    ",",
    formatlist(
      "\"%s\":{\"Value\": {\"Fn::GetAtt\":[\"ExecuteLambda\", \"%s\"]}}",
      ["Value", "Error"],
      ["Value", "Error"],
    ),
  )}
    }
  }
  EOF

  depends_on = [
    aws_secretsmanager_secret_version.db_user_privs_secret_version,
    aws_secretsmanager_secret_version.db_user_secret_version,
    module.rds_user_management_lambda
  ]
}
