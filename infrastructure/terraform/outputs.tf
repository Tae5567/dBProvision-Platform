output "db_endpoint" {
  description = "RDS instance hostname (without port)"
  value       = module.tenant_rds.db_endpoint
}

output "db_port" {
  description = "RDS instance port"
  value       = module.tenant_rds.db_port
}

output "db_arn" {
  description = "ARN of the RDS instance"
  value       = module.tenant_rds.db_arn
}

output "db_id" {
  description = "RDS instance identifier"
  value       = module.tenant_rds.db_id
}

output "db_name" {
  description = "Database name"
  value       = var.db_name
}

output "db_username" {
  description = "Master username"
  value       = var.db_username
  sensitive   = true
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret holding the DB password"
  value       = "arn:aws:secretsmanager:${var.aws_region}:*:secret:dbprovision/${var.tenant_id}/password"
}