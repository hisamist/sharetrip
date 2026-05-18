variable "environment" {
  description = "Deployment environment (e.g. production, staging)"
  type        = string
  default     = "production"
}

variable "app_image" {
  description = "Docker image for the ShareTrip application"
  type        = string
  default     = "ghcr.io/hisamist/sharetrip:latest"
}

variable "app_port" {
  description = "Host port the application is exposed on"
  type        = number
  default     = 8000
}

variable "postgres_user" {
  description = "PostgreSQL database username"
  type        = string
  default     = "sharetrip"
}

variable "postgres_password" {
  description = "PostgreSQL database password (sensitive)"
  type        = string
  sensitive   = true
}

variable "postgres_db" {
  description = "PostgreSQL database name"
  type        = string
  default     = "sharetrip"
}

variable "redis_url" {
  description = "Redis connection URL (derived from the redis container name)"
  type        = string
  default     = "redis://sharetrip_redis:6379/0"
}

variable "jwt_secret_key" {
  description = "Secret key used to sign JWT tokens (minimum 32 characters, sensitive)"
  type        = string
  sensitive   = true
}
