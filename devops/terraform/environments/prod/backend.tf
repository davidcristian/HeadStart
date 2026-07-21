# Remote state in S3 with DynamoDB locking. See devops/terraform/README.md.
# The state bucket is not committed. Pass it at init time:
#   terraform init -backend-config=backend.hcl
# or:
#   terraform init -backend-config="bucket=YOURNAME-headstart-tfstate"
# Copy backend.hcl.example → backend.hcl (gitignored) after bootstrap.
terraform {
  backend "s3" {
    key            = "prod/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "headstart-tflock"
    encrypt        = true
  }
}
