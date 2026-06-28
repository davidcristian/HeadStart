# Remote state in S3 with DynamoDB locking. See devops/terraform/README.md.
terraform {
  backend "s3" {
    bucket         = "CHANGEME-jobnotifier-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "jobnotifier-tflock"
    encrypt        = true
  }
}
