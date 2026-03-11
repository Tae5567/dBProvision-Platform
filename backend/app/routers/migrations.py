from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import hashlib

from app.models.database import get_db
from app.models.migration import Migration, MigrationRun, BulkMigrationJob, MigrationStatus
from app.models.tenant import TenantDatabase, DatabaseStatus
from app.services.migration_runner import MigrationRunner
from app.workers.tasks import run_bulk_migration_task

router = APIRouter(prefix="/api/v1/migrations", tags=["migrations"])

class CreateMigrationRequest(BaseModel):
    name: str
    version: int
    description: Optional[str]
    up_sql: str
    down_sql: Optional[str]
    created_by: str

class BulkMigrationRequest(BaseModel):
    migration_id: str
    target_env: str = "all"
    target_tenant_ids: List[str] = []
    created_by: str = "system"
    concurrency: int = 10

@router.post("/", status_code=201)
async def create_migration(
    request: CreateMigrationRequest,
    db: AsyncSession = Depends(get_db)
):
    checksum = hashlib.sha256(request.up_sql.encode()).hexdigest()
    
    migration = Migration(
        name=request.name,
        version=request.version,
        description=request.description,
        up_sql=request.up_sql,
        down_sql=request.down_sql,
        checksum=checksum,
        created_by=request.created_by
    )
    db.add(migration)
    await db.commit()
    await db.refresh(migration)
    return migration

@router.get("/")
async def list_migrations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Migration).order_by(Migration.version.desc())
    )
    return result.scalars().all()

@router.post("/bulk", status_code=202)
async def run_bulk_migration(
    request: BulkMigrationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Queue a bulk migration across multiple tenant databases."""
    
    migration = await db.get(Migration, request.migration_id)
    if not migration:
        raise HTTPException(404, "Migration not found")
    
    job = BulkMigrationJob(
        migration_id=request.migration_id,
        target_env=request.target_env,
        target_tenant_ids=request.target_tenant_ids,
        created_by=request.created_by
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    run_bulk_migration_task.delay(str(job.id), request.concurrency)
    
    return {"job_id": job.id, "message": "Bulk migration queued"}

@router.get("/bulk/{job_id}")
async def get_bulk_migration_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(BulkMigrationJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job

@router.post("/{migration_id}/apply/{db_id}")
async def apply_migration_to_db(
    migration_id: str,
    db_id: str,
    run_by: str = "api",
    db: AsyncSession = Depends(get_db)
):
    migration = await db.get(Migration, migration_id)
    tenant_db = await db.get(TenantDatabase, db_id)
    
    if not migration or not tenant_db:
        raise HTTPException(404, "Migration or database not found")
    
    runner = MigrationRunner(db)
    run = await runner.apply_migration(migration, tenant_db, run_by=run_by)
    return run

@router.post("/{migration_id}/rollback/{db_id}")
async def rollback_migration(
    migration_id: str,
    db_id: str,
    db: AsyncSession = Depends(get_db)
):
    migration = await db.get(Migration, migration_id)
    tenant_db = await db.get(TenantDatabase, db_id)
    
    if not migration:
        raise HTTPException(404, "Migration not found")
    if not migration.down_sql:
        raise HTTPException(400, "Migration has no rollback SQL")
    
    runner = MigrationRunner(db)
    await runner.rollback_migration(migration, tenant_db)
    return {"message": "Rollback completed"}