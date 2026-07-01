variable "environment" {
  type        = string
  description = "Environment name (dev, prod)."
}

variable "region" { type = string }

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}
variable "azs" {
  type = list(string)
}
variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.0.0/24", "10.20.1.0/24"]
}
variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "image_tag" {
  type    = string
  default = "latest"
}

# Secrets (provide via TF_VAR_* or a tfvars file kept out of git).
variable "db_password" {
  type      = string
  sensitive = true
}
variable "jwt_secret" {
  type        = string
  sensitive   = true
  description = "Secret used to sign access/refresh JWTs."
}
variable "credentials_secret_key" {
  type        = string
  sensitive   = true
  description = "Key used to encrypt per-site credentials at rest."
}

variable "db_username" {
  type    = string
  default = "jobnotifier"
}
variable "db_name" {
  type    = string
  default = "jobnotifier"
}

variable "cors_origins" {
  type        = list(string)
  description = "Allowed CORS origins (e.g. your ALB/app domain)."
  default     = []
}

variable "domain_name" {
  type        = string
  default     = ""
  description = "Optional custom hostname (e.g. jobs.example.com). Enables HTTPS when combined with route53_zone_id or acm_certificate_arn."
}

variable "route53_zone_id" {
  type        = string
  default     = ""
  description = "Route53 hosted zone for domain_name. Provisions ACM DNS validation and an ALB alias record."
}

variable "acm_certificate_arn" {
  type        = string
  default     = ""
  description = "Pre-validated ACM certificate ARN in the ALB region. Skips ACM creation when route53_zone_id is also set."
}

variable "ntfy_default_server_url" {
  type    = string
  default = "https://ntfy.sh"
}
variable "ntfy_default_topic" {
  type    = string
  default = "jobnotifier-change-me"
}

# Optional SMTP for password-reset and email notifications.
# When smtp_host is set, SMTP_PASSWORD (if provided) is stored in Secrets Manager.
variable "smtp_host" {
  type        = string
  default     = ""
  description = "SMTP relay hostname. Leave empty to disable outbound email."
}

variable "smtp_port" {
  type    = number
  default = 587
}

variable "smtp_user" {
  type    = string
  default = ""
}

variable "smtp_password" {
  type        = string
  sensitive   = true
  default     = ""
  description = "SMTP password or API key. Stored in Secrets Manager when non-empty."
}

variable "smtp_from" {
  type        = string
  default     = ""
  description = "From address for transactional email. Defaults to noreply@<domain_name> when domain_name is set."
}

variable "smtp_use_tls" {
  type    = bool
  default = true
}

# Sizing / resilience knobs (prod overrides these).
variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}
variable "db_multi_az" {
  type    = bool
  default = false
}
variable "db_deletion_protection" {
  type    = bool
  default = false
}
variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "ecs_cpu" {
  type        = number
  description = "Fargate CPU units for api, beat, migrate, and frontend tasks."
  default     = 256
}
variable "ecs_memory" {
  type        = number
  description = "Fargate memory (MiB) for api, beat, migrate, and frontend tasks."
  default     = 512
}
variable "worker_cpu" {
  type        = number
  description = "Fargate CPU units for the worker task (Playwright needs headroom)."
  default     = 1024
}
variable "worker_memory" {
  type        = number
  description = "Fargate memory (MiB) for the worker task (Chromium baseline ~512 MiB)."
  default     = 2048
}

variable "tags" {
  type    = map(string)
  default = {}
}
