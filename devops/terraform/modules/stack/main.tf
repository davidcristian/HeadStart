# Full JobNotifier stack for one environment. Each environment (dev, prod) calls
# this module with its own provider + remote state.

locals {
  name = "jobnotifier-${var.environment}"
  tags = merge(var.tags, {
    Project     = "JobNotifier"
    Environment = var.environment
    ManagedBy   = "terraform"
  })
  effective_cors = length(var.cors_origins) > 0 ? var.cors_origins : ["http://${module.alb.dns_name}"]
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
  repositories = ["jobnotifier-backend", "jobnotifier-frontend"]
  tags         = local.tags
}

module "secrets" {
  source       = "../secrets"
  name         = local.name
  secret_names = ["POSTGRES_PASSWORD", "JWT_SECRET", "CREDENTIALS_SECRET_KEY"]
  secret_values = {
    POSTGRES_PASSWORD      = var.db_password
    JWT_SECRET             = var.jwt_secret
    CREDENTIALS_SECRET_KEY = var.credentials_secret_key
  }
  tags = local.tags
}

module "iam" {
  source      = "../iam"
  name        = local.name
  secret_arns = values(module.secrets.secret_arns)
  tags        = local.tags
}

module "alb" {
  source            = "../alb"
  name              = local.name
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  security_group_id = module.security.alb_sg_id
  tags              = local.tags
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

module "ecs" {
  source                    = "../ecs"
  name                      = local.name
  region                    = var.region
  private_subnet_ids        = module.network.private_subnet_ids
  tasks_security_group_id   = module.security.tasks_sg_id
  execution_role_arn        = module.iam.execution_role_arn
  task_role_arn             = module.iam.task_role_arn
  backend_image             = module.ecr.repository_urls["jobnotifier-backend"]
  frontend_image            = module.ecr.repository_urls["jobnotifier-frontend"]
  image_tag                 = var.image_tag
  api_target_group_arn      = module.alb.api_target_group_arn
  frontend_target_group_arn = module.alb.frontend_target_group_arn

  environment = {
    ENVIRONMENT             = var.environment
    LOG_LEVEL               = "INFO"
    POSTGRES_HOST           = module.rds.address
    POSTGRES_PORT           = tostring(module.rds.port)
    POSTGRES_DB             = module.rds.db_name
    POSTGRES_USER           = var.db_username
    REDIS_HOST              = module.redis.address
    REDIS_PORT              = tostring(module.redis.port)
    CORS_ORIGINS            = join(",", local.effective_cors)
    NTFY_DEFAULT_SERVER_URL = var.ntfy_default_server_url
    NTFY_DEFAULT_TOPIC      = var.ntfy_default_topic
    SCHEDULER_TICK_SECONDS  = "30"
    SCHEDULER_MAX_CATCHUP   = "1"
  }

  secrets = {
    POSTGRES_PASSWORD      = module.secrets.secret_arns["POSTGRES_PASSWORD"]
    JWT_SECRET             = module.secrets.secret_arns["JWT_SECRET"]
    CREDENTIALS_SECRET_KEY = module.secrets.secret_arns["CREDENTIALS_SECRET_KEY"]
  }

  tags = local.tags
}
