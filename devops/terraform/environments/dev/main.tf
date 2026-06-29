module "stack" {
  source = "../../modules/stack"

  environment            = "dev"
  region                 = var.region
  azs                    = var.azs
  image_tag              = var.image_tag
  db_password            = var.db_password
  jwt_secret             = var.jwt_secret
  credentials_secret_key = var.credentials_secret_key
  cors_origins           = var.cors_origins
  domain_name            = var.domain_name
  route53_zone_id        = var.route53_zone_id
  acm_certificate_arn    = var.acm_certificate_arn
  ntfy_default_topic     = var.ntfy_default_topic

  # Dev: small + cheap, no deletion protection.
  db_instance_class      = "db.t4g.micro"
  db_multi_az            = false
  db_deletion_protection = false
  redis_node_type        = "cache.t4g.micro"
}
