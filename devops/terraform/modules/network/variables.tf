variable "name" {
  type        = string
  description = "Name prefix for tagging resources."
}

variable "cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.20.0.0/16"
}

variable "azs" {
  type        = list(string)
  description = "Availability zones to span."
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDRs for the public subnets (one per AZ)."
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDRs for the private subnets (one per AZ)."
}

variable "tags" {
  type        = map(string)
  description = "Common tags."
  default     = {}
}
