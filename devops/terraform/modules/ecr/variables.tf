variable "repositories" {
  type        = list(string)
  description = "ECR repository names to create."
}

variable "keep_images" {
  type        = number
  description = "How many recent images to retain per repository."
  default     = 10
}

variable "tags" {
  type    = map(string)
  default = {}
}
