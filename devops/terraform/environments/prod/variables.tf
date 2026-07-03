variable "region" {
  type    = string
  default = "us-east-2"
}

variable "azs" {
  type    = list(string)
  default = ["us-east-2a", "us-east-2b"]
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}

variable "credentials_secret_key" {
  type      = string
  sensitive = true
}

variable "cors_origins" {
  type        = list(string)
  description = "Set to your production domain(s)."
  default     = []
}

variable "domain_name" {
  type        = string
  description = "Custom hostname for HTTPS (e.g. jobs.example.com)."
  default     = ""
}

variable "route53_zone_id" {
  type        = string
  description = "Route53 zone for domain_name (ACM validation + ALB alias)."
  default     = ""
}

variable "acm_certificate_arn" {
  type        = string
  description = "Optional pre-validated ACM cert ARN instead of auto-provisioning."
  default     = ""
}

variable "ntfy_default_topic" {
  type    = string
  default = "headstart-change-me"
}

variable "smtp_host" {
  type        = string
  description = "SMTP relay for password reset and email notifications."
  default     = ""
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
  type      = string
  sensitive = true
  default   = ""
}

variable "smtp_from" {
  type        = string
  description = "From address. Defaults to noreply@<domain_name> when domain_name is set."
  default     = ""
}

variable "smtp_use_tls" {
  type    = bool
  default = true
}
