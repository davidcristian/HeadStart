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

variable "ntfy_default_topic" {
  type    = string
  default = "jobnotifier-change-me"
}
