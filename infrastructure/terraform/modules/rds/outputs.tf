output "db_endpoint" {
  description = "RDS instance hostname"
  value       = aws_db_instance.tenant.address
}

output "db_port" {
  description = "RDS instance port"
  value       = aws_db_instance.tenant.port
}

output "db_arn" {
  description = "RDS instance ARN"
  value       = aws_db_instance.tenant.arn
}

output "db_id" {
  description = "RDS instance identifier"
  value       = aws_db_instance.tenant.id
}