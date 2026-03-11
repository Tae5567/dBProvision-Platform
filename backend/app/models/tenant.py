from sqlalchemy import Column, String, Integer, DateTime, Enum, JSON, Boolean, Float
from sqlalchemy.sql import func
import enum
import uuid
from app.models.database import Base

class DatabaseStatus(str, enum.Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    MIGRATING = "migrating"
    BACKING_UP = "backing_up"
    SCALING = "scaling"
    ERROR = "error"
    DEPROVISIONED = "deprovisioned"

class DatabaseTier(str, enum.Enum):
    MICRO = "micro"       # db.t3.micro
    SMALL = "small"       # db.t3.small
    MEDIUM = "medium"     # db.t3.medium
    LARGE = "large"       # db.r6g.large
    XLARGE = "xlarge"     # db.r6g.xlarge

TIER_CONFIG = {
    DatabaseTier.MICRO:  {"instance_class": "db.t3.micro",   "storage": 20,  "cost_per_hour": 0.017},
    DatabaseTier.SMALL:  {"instance_class": "db.t3.small",   "storage": 50,  "cost_per_hour": 0.034},
    DatabaseTier.MEDIUM: {"instance_class": "db.t3.medium",  "storage": 100, "cost_per_hour": 0.068},
    DatabaseTier.LARGE:  {"instance_class": "db.r6g.large",  "storage": 200, "cost_per_hour": 0.240},
    DatabaseTier.XLARGE: {"instance_class": "db.r6g.xlarge", "storage": 500, "cost_per_hour": 0.480},
}

class TenantDatabase(Base):
    __tablename__ = "tenant_databases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    tenant_name = Column(String, nullable=False)
    environment = Column(String, nullable=False)  # prod, staging, dev
    
    # Database config
    db_identifier = Column(String, unique=True)   # RDS identifier
    db_host = Column(String)
    db_port = Column(Integer, default=5432)
    db_name = Column(String, nullable=False)
    db_username = Column(String, nullable=False)
    tier = Column(Enum(DatabaseTier), default=DatabaseTier.MICRO)
    
    # Status
    status = Column(Enum(DatabaseStatus), default=DatabaseStatus.PENDING)
    status_message = Column(String)
    
    # Infrastructure
    aws_region = Column(String, default="us-east-1")
    rds_arn = Column(String)
    terraform_workspace = Column(String)
    
    # Schema
    schema_version = Column(Integer, default=0)
    migrations_applied = Column(JSON, default=list)
    
    # Metadata
    tags = Column(JSON, default=dict)
    owner = Column(String)
    team = Column(String)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_backup_at = Column(DateTime(timezone=True))
    
    # Cost
    monthly_cost_estimate = Column(Float, default=0.0)
    
    # Feature flags
    multi_az = Column(Boolean, default=False)
    encryption_enabled = Column(Boolean, default=True)
    backup_enabled = Column(Boolean, default=True)
    monitoring_enabled = Column(Boolean, default=True)