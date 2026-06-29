variable "domain_name" {
  type        = string
  description = "Hostname to issue the certificate for (e.g. jobs.example.com)."
}

variable "route53_zone_id" {
  type        = string
  description = "Route53 hosted zone used for ACM DNS validation."
}

variable "tags" {
  type    = map(string)
  default = {}
}
