variable "name" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "security_group_id" { type = string }

variable "certificate_arn" {
  type        = string
  default     = null
  description = "ACM certificate ARN for HTTPS on port 443. When set, HTTP redirects to HTTPS."
}

variable "enable_deletion_protection" {
  type        = bool
  default     = false
  description = "Prevent accidental ALB destroy (enable on prod)."
}

variable "tags" {
  type    = map(string)
  default = {}
}
