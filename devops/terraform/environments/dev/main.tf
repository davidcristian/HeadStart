module "stack" {
  source = "../../modules/stack"

  environment        = "dev"
  region             = var.region
  azs                = var.azs
  image_tag              = var.image_tag
  db_password            = var.db_password
  jwt_secret             = var.jwt_secret
  credentials_secret_key = var.credentials_secret_key
  cors_origins           = var.cors_origins
  ntfy_default_topic     = var.ntfy_default_topic

  # Dev: small + cheap, no deletion protection.
  db_instance_class      = "db.t4g.micro"
  db_multi_az            = false
  db_deletion_protection = false
  redis_node_type        = "cache.t4g.micro"
}
