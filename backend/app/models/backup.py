from sqlalchemy import Column, String, Integer, DateTime, Enum, Float, Boolean
from sqlalchemy.sql import func
import enum
import uuid
from app.models.database import Base

class BackupType(str, enum.Enum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    PRE_MIGRATION = "pre_migration"
    SNAPSHOT = "snapshot"

class BackupStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

class Backup(Base):
    __tablename__ = "backups"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_db_id = Column(String, nullable=False, index=True)
    
    backup_type = Column(Enum(BackupType), nullable=False)
    status = Column(Enum(BackupStatus), default=BackupStatus.PENDING)
    
    # Storage
    s3_bucket = Column(String)
    s3_key = Column(String)
    size_bytes = Column(Integer)
    
    # RDS snapshot
    rds_snapshot_id = Column(String)
    rds_snapshot_arn = Column(String)
    
    # Retention
    expires_at = Column(DateTime(timezone=True))
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String)
    error_message = Column(String)