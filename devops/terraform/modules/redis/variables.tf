variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_id" { type = string }

variable "engine_version" {
  type    = string
  default = "7.1"
}
variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}
variable "parameter_group_name" {
  type    = string
  default = "default.redis7"
}

# When true, provision a Multi-AZ replication group with automatic failover
# instead of a single-node cluster (OPS-05 / OPS-49).
variable "automatic_failover" {
  type        = bool
  default     = false
  description = "Use a Multi-AZ replication group with automatic failover."
}

variable "num_cache_clusters" {
  type        = number
  default     = 2
  description = "Nodes in the replication group when automatic_failover is true (min 2)."

  validation {
    condition     = var.num_cache_clusters >= 2
    error_message = "num_cache_clusters must be at least 2 when using automatic failover."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
