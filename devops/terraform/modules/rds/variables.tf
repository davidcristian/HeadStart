variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_id" { type = string }

variable "engine_version" {
  type    = string
  default = "16.4"
}
variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}
variable "allocated_storage" {
  type    = number
  default = 20
}
variable "max_allocated_storage" {
  type    = number
  default = 100
}
variable "db_name" {
  type    = string
  default = "headstart"
}
variable "username" {
  type    = string
  default = "headstart"
}
variable "password" {
  type      = string
  sensitive = true
}
variable "multi_az" {
  type    = bool
  default = false
}
variable "backup_retention_days" {
  type    = number
  default = 7
}
variable "deletion_protection" {
  type    = bool
  default = false
}

# OPS-43: default false so parameter/engine changes wait for the next
# maintenance window instead of forcing an immediate reboot.
variable "apply_immediately" {
  type        = bool
  default     = false
  description = "Apply RDS modifications immediately (disruptive); prefer false."
}

variable "monitoring_interval" {
  type        = number
  default     = 60
  description = "Enhanced Monitoring interval in seconds (0 disables)."

  validation {
    condition     = contains([0, 1, 5, 10, 15, 30, 60], var.monitoring_interval)
    error_message = "monitoring_interval must be 0, 1, 5, 10, 15, 30, or 60."
  }
}

variable "performance_insights_retention_days" {
  type        = number
  default     = 7
  description = "Performance Insights retention (7 free tier; 31–731 paid)."

  validation {
    condition = (
      var.performance_insights_retention_days == 7
      || (
        var.performance_insights_retention_days >= 31
        && var.performance_insights_retention_days <= 731
      )
    )
    error_message = "performance_insights_retention_days must be 7 or 31–731."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
