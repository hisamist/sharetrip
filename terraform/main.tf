module "sharetrip" {
  source = "./modules/sharetrip-stack"

  environment       = var.environment
  app_image         = var.app_image
  app_port          = var.app_port
  postgres_user     = var.postgres_user
  postgres_password = var.postgres_password
  postgres_db       = var.postgres_db
  redis_url         = var.redis_url
  jwt_secret_key    = var.jwt_secret_key
}
