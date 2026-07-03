# Remote state in S3 with DynamoDB locking. See devops/terraform/README.md.
terraform {
  backend "s3" {
    bucket         = "CHANGEME-headstart-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "headstart-tflock"
    encrypt        = true
  }
}
