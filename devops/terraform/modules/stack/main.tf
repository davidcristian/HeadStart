# Full HeadStart stack for one environment. Each environment (beta, prod) calls
# this module with its own provider + remote state.

locals {
  name = "headstart-${var.environment}"
  tags = merge(var.tags, {
    Project     = "HeadStart"
    Environment = var.environment
    ManagedBy   = "terraform"
  })

  create_acm = (
    var.domain_name != "" &&
    var.route53_zone_id != "" &&
    var.acm_certificate_arn == ""
  )
  use_route53_alias = var.domain_name != "" && var.route53_zone_id != ""

  certificate_arn = var.acm_certificate_arn != "" ? var.acm_certificate_arn : (
    local.create_acm ? module.acm[0].certificate_arn : ""
  )
  https_enabled = local.certificate_arn != ""

  app_base_url = (
    local.https_enabled && var.domain_name != "" ?
    "https://${var.domain_name}" :
    "http://${module.alb.dns_name}"
  )

  effective_cors = length(var.cors_origins) > 0 ? var.cors_origins : [local.app_base_url]

  effective_smtp_from = var.smtp_from != "" ? var.smtp_from : (
    var.domain_name != "" ? "noreply@${var.domain_name}" : ""
  )

  base_secret_values = {
    POSTGRES_PASSWORD      = var.db_password
    JWT_SECRET             = var.jwt_secret
    CREDENTIALS_SECRET_KEY = var.credentials_secret_key
  }
  smtp_secret_values = var.smtp_password != "" ? { SMTP_PASSWORD = var.smtp_password } : {}
  secret_values      = merge(local.base_secret_values, local.smtp_secret_values)
}

module "network" {
  source               = "../network"
  name                 = local.name
  cidr                 = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  tags                 = local.tags
}

module "security" {
  source = "../security"
  name   = local.name
  vpc_id = module.network.vpc_id
  tags   = local.tags
}

module "ecr" {
  source       = "../ecr"
  repositories = ["headstart-backend", "headstart-backend-worker", "headstart-frontend"]
  tags         = local.tags
}

module "secrets" {
  source        = "../secrets"
  name          = local.name
  secret_names  = keys(local.secret_values)
  secret_values = local.secret_values
  tags          = local.tags
}

module "iam" {
  source      = "../iam"
  name        = local.name
  secret_arns = values(module.secrets.secret_arns)
  tags        = local.tags
}

module "acm" {
  count  = local.create_acm ? 1 : 0
  source = "../acm"

  domain_name     = var.domain_name
  route53_zone_id = var.route53_zone_id
  tags            = local.tags
}

module "alb" {
  source            = "../alb"
  name              = local.name
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  security_group_id = module.security.alb_sg_id
  certificate_arn   = local.https_enabled ? local.certificate_arn : null
  tags              = local.tags
}

resource "aws_route53_record" "app" {
  count = local.use_route53_alias ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = module.alb.dns_name
    zone_id                = module.alb.zone_id
    evaluate_target_health = true
  }
}

module "rds" {
  source              = "../rds"
  name                = local.name
  subnet_ids          = module.network.private_subnet_ids
  security_group_id   = module.security.rds_sg_id
  instance_class      = var.db_instance_class
  multi_az            = var.db_multi_az
  deletion_protection = var.db_deletion_protection
  db_name             = var.db_name
  username            = var.db_username
  password            = var.db_password
  tags                = local.tags
}

module "redis" {
  source            = "../redis"
  name              = local.name
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.security.redis_sg_id
  node_type         = var.redis_node_type
  tags              = local.tags
}

locals {
  smtp_ecs_environment = var.smtp_host != "" ? merge(
    {
      SMTP_HOST    = var.smtp_host
      SMTP_PORT    = tostring(var.smtp_port)
      SMTP_USER    = var.smtp_user
      SMTP_USE_TLS = var.smtp_use_tls ? "true" : "false"
    },
    local.effective_smtp_from != "" ? { SMTP_FROM = local.effective_smtp_from } : {},
  ) : {}

  ecs_environment = merge(
    {
      ENVIRONMENT                      = var.environment
      LOG_LEVEL                        = "INFO"
      POSTGRES_HOST                    = module.rds.address
      POSTGRES_PORT                    = tostring(module.rds.port)
      POSTGRES_DB                      = module.rds.db_name
      POSTGRES_USER                    = var.db_username
      REDIS_HOST                       = module.redis.address
      REDIS_PORT                       = tostring(module.redis.port)
      CORS_ORIGINS                     = join(",", local.effective_cors)
      FRONTEND_BASE_URL                = local.app_base_url
      NTFY_DEFAULT_SERVER_URL          = var.ntfy_default_server_url
      NTFY_DEFAULT_TOPIC               = var.ntfy_default_topic
      SCHEDULER_TICK_SECONDS           = "30"
      PLAYWRIGHT_NAVIGATION_TIMEOUT_MS = "30000"
      PLAYWRIGHT_MAX_RETRIES           = "1"
    },
    local.smtp_ecs_environment,
  )

  ecs_secrets = merge(
    {
      POSTGRES_PASSWORD      = module.secrets.secret_arns["POSTGRES_PASSWORD"]
      JWT_SECRET             = module.secrets.secret_arns["JWT_SECRET"]
      CREDENTIALS_SECRET_KEY = module.secrets.secret_arns["CREDENTIALS_SECRET_KEY"]
    },
    var.smtp_password != "" ? {
      SMTP_PASSWORD = module.secrets.secret_arns["SMTP_PASSWORD"]
    } : {},
  )
}

module "ecs" {
  source                    = "../ecs"
  name                      = local.name
  region                    = var.region
  private_subnet_ids        = module.network.private_subnet_ids
  tasks_security_group_id   = module.security.tasks_sg_id
  execution_role_arn        = module.iam.execution_role_arn
  task_role_arn             = module.iam.task_role_arn
  backend_image             = module.ecr.repository_urls["headstart-backend"]
  worker_backend_image      = module.ecr.repository_urls["headstart-backend-worker"]
  frontend_image            = module.ecr.repository_urls["headstart-frontend"]
  image_tag                 = var.image_tag
  cpu                       = var.ecs_cpu
  memory                    = var.ecs_memory
  worker_cpu                = var.worker_cpu
  worker_memory             = var.worker_memory
  api_target_group_arn      = module.alb.api_target_group_arn
  frontend_target_group_arn = module.alb.frontend_target_group_arn

  environment = local.ecs_environment
  secrets     = local.ecs_secrets

  tags = local.tags
}
