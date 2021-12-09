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
