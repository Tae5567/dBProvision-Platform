from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App
    app_name: str = "DBProvision"
    environment: str = "development"
    secret_key: str = "change-in-production"
    
    # Management Database
    mgmt_db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dbprovision"
    mgmt_db_sync_url: str = "postgresql://postgres:postgres@localhost:5432/dbprovision"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    
    # RDS Defaults
    rds_instance_class: str = "db.t3.micro"
    rds_engine_version: str = "15.4"
    rds_allocated_storage: int = 20
    rds_subnet_group: str = "default"
    rds_security_group_id: str = ""
    
    # Terraform
    terraform_dir: str = "./infrastructure/terraform"
    terraform_state_bucket: str = "dbprovision-tf-state"
    
    # Backup
    backup_s3_bucket: str = "dbprovision-backups"
    backup_retention_days: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()