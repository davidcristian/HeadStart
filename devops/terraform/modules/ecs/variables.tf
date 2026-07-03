variable "name" {
  type        = string
  description = "Cluster/log-group name (e.g. headstart-dev)."
}

variable "service_prefix" {
  type        = string
  description = "Prefix for ECS service + task family names (kept stable across envs so deploy.sh can target them)."
  default     = "headstart"
}

variable "region" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "tasks_security_group_id" { type = string }
variable "execution_role_arn" { type = string }
variable "task_role_arn" { type = string }

variable "backend_image" {
  type        = string
  description = "Backend ECR repository URL (without tag)."
}
variable "worker_backend_image" {
  type        = string
  description = "Worker backend ECR repository URL (without tag); includes Playwright."
}
variable "frontend_image" {
  type        = string
  description = "Frontend ECR repository URL (without tag)."
}
variable "image_tag" {
  type    = string
  default = "latest"
}

variable "api_target_group_arn" { type = string }
variable "frontend_target_group_arn" { type = string }

variable "environment" {
  type        = map(string)
  description = "Plain environment variables shared by backend services."
  default     = {}
}

variable "secrets" {
  type        = map(string)
  description = "Map of env var name -> Secrets Manager ARN to inject."
  default     = {}
}

variable "cpu" {
  type    = number
  default = 256
}
variable "memory" {
  type    = number
  default = 512
}
variable "worker_cpu" {
  type    = number
  default = 1024
}
variable "worker_memory" {
  type    = number
  default = 2048
}

variable "desired_counts" {
  type = object({
    api      = number
    frontend = number
    worker   = number
    beat     = number
  })
  default = {
    api      = 1
    frontend = 1
    worker   = 1
    beat     = 1 # exactly one beat to avoid duplicate scheduling
  }
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
