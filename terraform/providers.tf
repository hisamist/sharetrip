terraform {
  required_version = ">= 1.6"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }

  # Local backend — for a real deployment, use a remote backend:
  # backend "s3" { bucket = "..." key = "sharetrip/terraform.tfstate" region = "..." }
  # or: backend "remote" { organization = "..." workspaces { name = "sharetrip" } }
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "docker" {}
