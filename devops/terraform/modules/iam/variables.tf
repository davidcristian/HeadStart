variable "name" { type = string }

variable "secret_arns" {
  type        = list(string)
  description = "Secret ARNs the execution role may read."
  default     = []
}

variable "secrets_kms_key_arn" {
  type        = string
  description = "CMK ARN for Secrets Manager secrets (kms:Decrypt for GetSecretValue)."
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
