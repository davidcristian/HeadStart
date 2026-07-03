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
variable "tags" {
  type    = map(string)
  default = {}
}
