output "app_url" {
  description = "Base URL for the ShareTrip application"
  value       = "http://localhost:${var.app_port}"
}

output "api_docs_url" {
  description = "URL for the interactive API documentation (Swagger UI)"
  value       = "http://localhost:${var.app_port}/docs"
}

output "network_name" {
  description = "Docker network used by the stack"
  value       = module.sharetrip.network_name
}

output "postgres_container_name" {
  description = "Name of the PostgreSQL container"
  value       = module.sharetrip.postgres_container_name
}

output "redis_container_name" {
  description = "Name of the Redis container"
  value       = module.sharetrip.redis_container_name
}

output "app_container_name" {
  description = "Name of the ShareTrip application container"
  value       = module.sharetrip.app_container_name
}
