module "stack" {
  source = "../../modules/stack"

  environment            = "prod"
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

  # Distinct from beta's 10.20.0.0/16 so VPC peering / shared routing stays unambiguous (OPS-30).
  vpc_cidr             = "10.30.0.0/16"
  public_subnet_cidrs  = ["10.30.0.0/24", "10.30.1.0/24"]
  private_subnet_cidrs = ["10.30.10.0/24", "10.30.11.0/24"]

  # Prod: HA database, longer backups/logs, deletion protection + final
  # snapshot required (OPS-48), Redis failover.
  db_instance_class        = "db.t4g.small"
  db_multi_az              = true
  db_deletion_protection   = true
  alb_deletion_protection  = true
  db_backup_retention_days = 30
  log_retention_days       = 90
  redis_node_type          = "cache.t4g.small"
  redis_automatic_failover = true
  redis_num_cache_clusters = 2
}
