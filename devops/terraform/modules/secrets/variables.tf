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

variable "tags" {
  type    = map(string)
  default = {}
}
