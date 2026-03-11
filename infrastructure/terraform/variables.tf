variable "tenant_id" {
  description = "Unique identifier for the tenant (e.g. acme-corp)"
  type        = string
}

variable "environment" {
  description = "Deployment environment: dev, staging, or prod"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "db_identifier" {
  description = "RDS instance identifier — must be unique across your AWS account"
  type        = string
}

variable "db_name" {
  description = "Name of the initial database to create inside the instance"
  type        = string
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16.6"
}

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "rds_subnet_group" {
  description = "Name of the DB subnet group"
  type        = string
  default     = "default"
}

variable "rds_security_group_id" {
  description = "Security group ID to attach to the RDS instance"
  type        = string
  default     = ""
}

variable "multi_az" {
  description = "Enable Multi-AZ deployment for high availability"
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Prevent accidental deletion of the RDS instance"
  type        = bool
  default     = false
}

variable "backups_bucket" {
  description = "S3 bucket name for database backups"
  type        = string
  default     = ""
}