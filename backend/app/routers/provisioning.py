from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.database import get_db
from app.models.tenant import TenantDatabase, DatabaseStatus, DatabaseTier
from app.services.provisioner import ProvisioningService
from app.workers.tasks import provision_database_task

router = APIRouter(prefix="/api/v1/databases", tags=["provisioning"])

class ProvisionRequest(BaseModel):
    tenant_id: str
    tenant_name: str
    environment: str  # prod, staging, dev
    db_name: str
    owner: str
    team: str
    tier: DatabaseTier = DatabaseTier.MICRO
    multi_az: bool = False
    tags: dict = {}
    aws_region: str = "us-east-1"

class DatabaseResponse(BaseModel):
    id: str
    tenant_id: str
    tenant_name: str
    environment: str
    db_identifier: str
    db_host: Optional[str]
    db_port: int
    db_name: str
    status: str
    status_message: Optional[str]
    tier: str
    schema_version: int
    monthly_cost_estimate: float
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

@router.post("/provision", response_model=DatabaseResponse, status_code=202)
async def provision_database(
    request: ProvisionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Provision a new database for a tenant. Returns immediately, provisioning runs async."""
    
    # Check for duplicate
    existing = await db.execute(
        select(TenantDatabase).where(
            TenantDatabase.tenant_id == request.tenant_id,
            TenantDatabase.environment == request.environment
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Database already exists for tenant {request.tenant_id} in {request.environment}")
    
    # Create record
    tenant_db = TenantDatabase(
        tenant_id=request.tenant_id,
        tenant_name=request.tenant_name,
        environment=request.environment,
        db_identifier=f"tenant-{request.tenant_id}-{request.environment}",
        db_name=request.db_name,
        db_username=f"admin{''.join(c for c in request.tenant_id if c.isalnum())[:10]}",
        tier=request.tier,
        owner=request.owner,
        team=request.team,
        tags=request.tags,
        aws_region=request.aws_region,
        multi_az=request.multi_az,
        status=DatabaseStatus.PENDING
    )
    
    db.add(tenant_db)
    await db.commit()
    await db.refresh(tenant_db)
    
    # Queue async provisioning
    provision_database_task.delay(str(tenant_db.id))
    
    return tenant_db

@router.get("/", response_model=List[DatabaseResponse])
async def list_databases(
    environment: Optional[str] = None,
    team: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(TenantDatabase)
    if environment:
        query = query.where(TenantDatabase.environment == environment)
    if team:
        query = query.where(TenantDatabase.team == team)
    if status:
        query = query.where(TenantDatabase.status == status)
    
    result = await db.execute(query.order_by(TenantDatabase.created_at.desc()))
    return result.scalars().all()

@router.get("/{db_id}", response_model=DatabaseResponse)
async def get_database(db_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TenantDatabase).where(TenantDatabase.id == db_id)
    )
    tenant_db = result.scalar_one_or_none()
    if not tenant_db:
        raise HTTPException(404, "Database not found")
    return tenant_db

@router.delete("/{db_id}")
async def deprovision_database(
    db_id: str,
    force: bool = False,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(TenantDatabase).where(TenantDatabase.id == db_id))
    tenant_db = result.scalar_one_or_none()
    if not tenant_db:
        raise HTTPException(404, "Database not found")
    
    service = ProvisioningService(db)
    await service.deprovision_database(tenant_db, force=force)
    return {"message": "Deprovisioning initiated"}