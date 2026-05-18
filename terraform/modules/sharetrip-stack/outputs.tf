output "network_name" {
  description = "Name of the Docker network shared by all ShareTrip containers"
  value       = docker_network.sharetrip.name
}

output "postgres_container_name" {
  description = "Name of the PostgreSQL container"
  value       = docker_container.postgres.name
}

output "redis_container_name" {
  description = "Name of the Redis container"
  value       = docker_container.redis.name
}

output "app_container_name" {
  description = "Name of the ShareTrip application container"
  value       = docker_container.app.name
}
