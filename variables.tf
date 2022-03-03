variable "create_kms_iam_policy" {
  type        = bool
  default     = false
  description = "Create a IAM policy for permissions on KMS keys for password rotation Lambda"
}

variable "create_vpc_rds_endpoint" {
  type        = bool
  default     = false
  description = "Create a VPC endpoint for RDS"
}

variable "create_vpc_secm_endpoint" {
  type        = bool
  default     = false
  description = "Create a VPC endpoint for SSM"
}

variable "deploy_password_rotation" {
  type        = bool
  default     = false
  description = "Deploy the Password rotation module"
}

variable "env_master_username" {
  type        = string
  description = "Default master username of RDS instances"
}

variable "env_secret_name" {
  type        = string
  description = "Secret in which the master user is saved"
}

variable "kms_key_id" {
  type        = string
  description = "ID of KMS key used for secrets"
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of KMS key used for secrets"
}

variable "sql_users" {
  description = "List of SQL users which should be managed"
}

variable "subnet_ids" {
  type        = list(string)
  description = "List of subnet IDs to deploy Lambda in"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to attach to lambda"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID to deploy lambda"
}
