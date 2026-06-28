variable "name" { type = string }

variable "secret_arns" {
  type        = list(string)
  description = "Secret ARNs the execution role may read."
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
