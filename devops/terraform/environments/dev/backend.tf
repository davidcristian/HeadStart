# Remote state in S3 with DynamoDB locking. Create the bucket + table once
# (see devops/terraform/README.md), then update the placeholders below or pass
# them via `terraform init -backend-config=...`.
terraform {
  backend "s3" {
    bucket         = "CHANGEME-jobnotifier-tfstate"
    key            = "dev/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "jobnotifier-tflock"
    encrypt        = true
  }
}
