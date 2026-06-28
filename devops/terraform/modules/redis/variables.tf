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
variable "tags" {
  type    = map(string)
  default = {}
}
