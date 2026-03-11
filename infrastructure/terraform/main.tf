terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "s3" {
    bucket         = "dbprovision-tf-state-587764055032"
    key            = "tenants/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "dbprovision-tf-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

module "tenant_rds" {
  source              = "./modules/rds"
  tenant_id           = var.tenant_id
  environment         = var.environment
  db_identifier       = var.db_identifier
  db_name             = var.db_name
  db_username         = var.db_username
  instance_class      = var.instance_class
  allocated_storage   = var.allocated_storage
  engine_version      = var.engine_version
  subnet_group_name   = var.rds_subnet_group
  security_group_id   = var.rds_security_group_id
  multi_az            = var.multi_az
  deletion_protection = var.deletion_protection
  aws_region          = var.aws_region
  backups_bucket      = var.backups_bucket
}