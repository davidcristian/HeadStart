module "stack" {
  source = "../../modules/stack"

  environment        = "prod"
  region             = var.region
  azs                = var.azs
  image_tag              = var.image_tag
  db_password            = var.db_password
  jwt_secret             = var.jwt_secret
  credentials_secret_key = var.credentials_secret_key
  cors_origins           = var.cors_origins
  ntfy_default_topic     = var.ntfy_default_topic

  # Prod: HA database, deletion protection, larger nodes.
  db_instance_class      = "db.t4g.small"
  db_multi_az            = true
  db_deletion_protection = true
  redis_node_type        = "cache.t4g.small"
}
