variable "name" {
  type        = string
  description = "Secret name prefix (e.g. headstart-beta)."
}

variable "secret_names" {
  type        = list(string)
  description = "Secret keys to create (non-sensitive; used as resource keys)."
}

variable "secret_values" {
  type        = map(string)
  description = "Map of secret key -> value. Sensitive; never iterated directly."
  sensitive   = true
}

variable "recovery_window_in_days" {
  type        = number
  description = "Days Secrets Manager retains a deleted secret before purge (7 to 30, or 0 for immediate)."
  default     = 30

  validation {
    condition     = var.recovery_window_in_days == 0 || (var.recovery_window_in_days >= 7 && var.recovery_window_in_days <= 30)
    error_message = "recovery_window_in_days must be 0 (force delete) or between 7 and 30."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
