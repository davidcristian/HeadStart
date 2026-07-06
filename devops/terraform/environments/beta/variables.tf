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
  type    = list(string)
  default = []
}

variable "domain_name" {
  type    = string
  default = ""
}

variable "route53_zone_id" {
  type    = string
  default = ""
}

variable "acm_certificate_arn" {
  type    = string
  default = ""
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
  type    = string
  default = ""
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
  type    = string
  default = ""
}

variable "smtp_use_tls" {
  type    = bool
  default = true
}
