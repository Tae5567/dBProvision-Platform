from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.models.database import get_db
from app.models.backup import Backup, BackupType
from app.models.tenant import TenantDatabase
from app.services.backup_manager import BackupManager
from app.workers.tasks import create_backup_task

router = APIRouter(prefix="/api/v1/backups", tags=["backups"])

@router.post("/{db_id}/snapshot", status_code=202)
async def create_backup(
    db_id: str,
    backup_type: BackupType = BackupType.MANUAL,
    created_by: str = "api",
    db: AsyncSession = Depends(get_db)
):
    tenant_db = await db.get(TenantDatabase, db_id)
    if not tenant_db:
        raise HTTPException(404, "Database not found")
    
    create_backup_task.delay(db_id, backup_type.value, created_by)
    return {"message": "Backup initiated", "tenant_db_id": db_id}

@router.get("/{db_id}")
async def list_backups(db_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Backup)
        .where(Backup.tenant_db_id == db_id)
        .order_by(Backup.created_at.desc())
    )
    return result.scalars().all()

@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    target_identifier: str,
    db: AsyncSession = Depends(get_db)
):
    backup = await db.get(Backup, backup_id)
    if not backup:
        raise HTTPException(404, "Backup not found")
    
    tenant_db = await db.get(TenantDatabase, backup.tenant_db_id)
    
    manager = BackupManager(db)
    new_id = await manager.restore_from_snapshot(backup, tenant_db, target_identifier)
    return {"message": "Restore initiated", "new_db_identifier": new_id}