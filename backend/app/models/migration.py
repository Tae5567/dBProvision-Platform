from sqlalchemy import Column, String, Integer, DateTime, Enum, JSON, Text, ForeignKey
from sqlalchemy.sql import func
import enum
import uuid
from app.models.database import Base

class MigrationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class Migration(Base):
    __tablename__ = "migrations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(Text)
    
    # SQL content
    up_sql = Column(Text, nullable=False)
    down_sql = Column(Text)   # rollback SQL
    checksum = Column(String) # SHA256 of up_sql
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String)

class MigrationRun(Base):
    __tablename__ = "migration_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    migration_id = Column(String, ForeignKey("migrations.id"))
    tenant_db_id = Column(String, ForeignKey("tenant_databases.id"))
    
    status = Column(Enum(MigrationStatus), default=MigrationStatus.PENDING)
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    run_by = Column(String)

class BulkMigrationJob(Base):
    __tablename__ = "bulk_migration_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    migration_id = Column(String, ForeignKey("migrations.id"))
    
    target_env = Column(String)  # all, prod, staging, dev
    target_tenant_ids = Column(JSON, default=list)  # empty = all
    
    total_databases = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    
    status = Column(Enum(MigrationStatus), default=MigrationStatus.PENDING)
    results = Column(JSON, default=dict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_by = Column(String)