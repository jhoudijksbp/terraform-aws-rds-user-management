output "arn" {
  value       = module.rds_user_management_lambda.arn
  description = "ARN of the Lambda"
}

output "name" {
  value       = module.rds_user_management_lambda.name
  description = "Name of the Lambda"
}

output "security_group_id" {
  value       = module.rds_user_management_lambda.security_group_id
  description = "Lambda Security Group ID"
}
