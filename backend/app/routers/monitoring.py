from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.models.database import get_db
from app.models.tenant import TenantDatabase
from app.services.query_analyzer import QueryAnalyzer
from app.services.provisioner import ProvisioningService

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])
analyzer = QueryAnalyzer()

@router.get("/{db_id}/health")
async def get_database_health(db_id: str, db: AsyncSession = Depends(get_db)):
    tenant_db = await db.get(TenantDatabase, db_id)
    if not tenant_db or not tenant_db.db_host:
        raise HTTPException(404, "Database not found or not yet provisioned")
    
    password = await ProvisioningService(db)._get_db_password(db_id)
    health = await analyzer.get_db_health(
        tenant_db.db_host, tenant_db.db_port,
        tenant_db.db_name, tenant_db.db_username, password
    )
    return health

@router.get("/{db_id}/slow-queries")
async def get_slow_queries(
    db_id: str,
    threshold_ms: float = 1000.0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    tenant_db = await db.get(TenantDatabase, db_id)
    if not tenant_db:
        raise HTTPException(404, "Database not found")
    
    password = await ProvisioningService(db)._get_db_password(db_id)
    queries = await analyzer.get_slow_queries(
        tenant_db.db_host, tenant_db.db_port,
        tenant_db.db_name, tenant_db.db_username, password,
        threshold_ms=threshold_ms, limit=limit
    )
    return queries

@router.get("/{db_id}/index-suggestions")
async def get_index_suggestions(db_id: str, db: AsyncSession = Depends(get_db)):
    tenant_db = await db.get(TenantDatabase, db_id)
    if not tenant_db:
        raise HTTPException(404, "Database not found")
    
    password = await ProvisioningService(db)._get_db_password(db_id)
    suggestions = await analyzer.get_index_suggestions(
        tenant_db.db_host, tenant_db.db_port,
        tenant_db.db_name, tenant_db.db_username, password
    )
    return suggestions

@router.get("/overview")
async def get_fleet_overview(db: AsyncSession = Depends(get_db)):
    """High-level fleet stats for the dashboard."""
    from sqlalchemy import func
    from app.models.tenant import DatabaseStatus
    
    total = await db.scalar(select(func.count(TenantDatabase.id)))
    active = await db.scalar(
        select(func.count(TenantDatabase.id))
        .where(TenantDatabase.status == DatabaseStatus.ACTIVE)
    )
    errored = await db.scalar(
        select(func.count(TenantDatabase.id))
        .where(TenantDatabase.status == DatabaseStatus.ERROR)
    )
    total_cost = await db.scalar(
        select(func.sum(TenantDatabase.monthly_cost_estimate))
    )
    
    return {
        "total_databases": total,
        "active": active,
        "errored": errored,
        "provisioning": total - active - errored,
        "total_monthly_cost": float(total_cost or 0),
    }