variable "region" {
  type    = string
  default = "us-east-2"
}

# Required: pin the AWS account this env may target so a wrong ambient
# credential cannot apply prod into another account (OPS-31).
variable "aws_account_id" {
  type        = string
  description = "12-digit AWS account ID allowed for this environment's provider."

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account ID."
  }
}

variable "azs" {
  type    = list(string)
  default = ["us-east-2a", "us-east-2b"]
}

# Required: pin ECS task images to an immutable tag (git SHA). Floating
# "latest" is rejected so a recycle cannot silently pull a different build (OPS-07).
variable "image_tag" {
  type        = string
  description = "Immutable container image tag (git SHA). Do not use latest."

  validation {
    condition = (
      length(trimspace(var.image_tag)) > 0 &&
      lower(trimspace(var.image_tag)) != "latest"
    )
    error_message = "image_tag must be a non-empty immutable tag (git SHA), not latest."
  }
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

# Required: ntfy.sh topics are public by name — never ship a guessable default (OPS-16).
variable "ntfy_default_topic" {
  type        = string
  description = "Unguessable ntfy topic for the seeded default notification target."

  validation {
    condition = (
      length(trimspace(var.ntfy_default_topic)) > 0 &&
      !strcontains(lower(var.ntfy_default_topic), "change-me")
    )
    error_message = "ntfy_default_topic must be a non-empty unguessable value (not a change-me placeholder)."
  }
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
