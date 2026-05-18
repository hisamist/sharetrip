terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# ─── Network ────────────────────────────────────────────────────────────────
resource "docker_network" "sharetrip" {
  name = "sharetrip_${var.environment}"
}

# ─── Volumes ────────────────────────────────────────────────────────────────
resource "docker_volume" "postgres_data" {
  name = "sharetrip_${var.environment}_postgres_data"
}

resource "docker_volume" "redis_data" {
  name = "sharetrip_${var.environment}_redis_data"
}

# ─── PostgreSQL ─────────────────────────────────────────────────────────────
resource "docker_container" "postgres" {
  name  = "sharetrip_${var.environment}_postgres"
  image = "postgres:16-alpine"

  restart = "unless-stopped"

  env = [
    "POSTGRES_USER=${var.postgres_user}",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "POSTGRES_DB=${var.postgres_db}",
  ]

  volumes {
    volume_name    = docker_volume.postgres_data.name
    container_path = "/var/lib/postgresql/data"
  }

  networks_advanced {
    name = docker_network.sharetrip.name
  }

  healthcheck {
    test         = ["CMD-SHELL", "pg_isready -U ${var.postgres_user} -d ${var.postgres_db}"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 5
    start_period = "30s"
  }
}

# ─── Redis ──────────────────────────────────────────────────────────────────
resource "docker_container" "redis" {
  name  = "sharetrip_${var.environment}_redis"
  image = "redis:7-alpine"

  restart  = "unless-stopped"
  command  = ["redis-server", "--appendonly", "yes"]

  volumes {
    volume_name    = docker_volume.redis_data.name
    container_path = "/data"
  }

  networks_advanced {
    name = docker_network.sharetrip.name
  }
}

# ─── App ────────────────────────────────────────────────────────────────────
resource "docker_container" "app" {
  name  = "sharetrip_${var.environment}_app"
  image = var.app_image

  restart = "unless-stopped"

  depends_on = [
    docker_container.postgres,
    docker_container.redis,
  ]

  env = [
    "DATABASE_URL=postgresql://${var.postgres_user}:${var.postgres_password}@${docker_container.postgres.name}:5432/${var.postgres_db}",
    "REDIS_URL=${var.redis_url}",
    "JWT_SECRET_KEY=${var.jwt_secret_key}",
    "APP_ENV=${var.environment}",
  ]

  ports {
    internal = 8000
    external = var.app_port
  }

  networks_advanced {
    name = docker_network.sharetrip.name
  }
}
