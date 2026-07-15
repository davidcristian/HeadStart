module "stack" {
  source = "../../modules/stack"

  environment            = "beta"
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
  smtp_host              = var.smtp_host
  smtp_port              = var.smtp_port
  smtp_user              = var.smtp_user
  smtp_password          = var.smtp_password
  smtp_from              = var.smtp_from
  smtp_use_tls           = var.smtp_use_tls

  # Explicit beta CIDR (stack default); prod uses 10.30.0.0/16 (OPS-30).
  vpc_cidr             = "10.20.0.0/16"
  public_subnet_cidrs  = ["10.20.0.0/24", "10.20.1.0/24"]
  private_subnet_cidrs = ["10.20.10.0/24", "10.20.11.0/24"]

  # Beta: small + cheap, no deletion protection.
  db_instance_class      = "db.t4g.micro"
  db_multi_az            = false
  db_deletion_protection = false
  redis_node_type        = "cache.t4g.micro"
}
