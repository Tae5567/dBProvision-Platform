from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List
import asyncpg
import boto3

from app.models.database import get_db
from app.models.tenant import TenantDatabase

router = APIRouter(prefix="/api/v1/access", tags=["access"])

class GrantPermissionRequest(BaseModel):
    username: str
    permissions: List[str]  # SELECT, INSERT, UPDATE, DELETE, ALL
    schemas: List[str] = ["public"]
    tables: List[str] = []  # empty = all tables

class RevokePermissionRequest(BaseModel):
    username: str
    permissions: List[str]
    schemas: List[str] = ["public"]

@router.post("/{db_id}/grant")
async def grant_permissions(
    db_id: str,
    request: GrantPermissionRequest,
    db: AsyncSession = Depends(get_db)
):
    tenant_db = await db.get(TenantDatabase, db_id)
    if not tenant_db:
        raise HTTPException(404, "Database not found")
    
    conn = await _get_conn(tenant_db)
    try:
        for schema in request.schemas:
            privs = ", ".join(request.permissions)
            if request.tables:
                for table in request.tables:
                    await conn.execute(
                        f"GRANT {privs} ON TABLE {schema}.{table} TO {request.username}"
                    )
            else:
                await conn.execute(
                    f"GRANT {privs} ON ALL TABLES IN SCHEMA {schema} TO {request.username}"
                )
                await conn.execute(
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
                    f"GRANT {privs} ON TABLES TO {request.username}"
                )
    finally:
        await conn.close()
    
    return {"message": f"Permissions granted to {request.username}"}

@router.post("/{db_id}/revoke")
async def revoke_permissions(
    db_id: str,
    request: RevokePermissionRequest,
    db: AsyncSession = Depends(get_db)
):
    tenant_db = await db.get(TenantDatabase, db_id)
    if not tenant_db:
        raise HTTPException(404, "Database not found")
    
    conn = await _get_conn(tenant_db)
    try:
        for schema in request.schemas:
            privs = ", ".join(request.permissions)
            await conn.execute(
                f"REVOKE {privs} ON ALL TABLES IN SCHEMA {schema} FROM {request.username}"
            )
    finally:
        await conn.close()
    
    return {"message": f"Permissions revoked from {request.username}"}

@router.get("/{db_id}/users")
async def list_users(db_id: str, db: AsyncSession = Depends(get_db)):
    tenant_db = await db.get(TenantDatabase, db_id)
    conn = await _get_conn(tenant_db)
    try:
        rows = await conn.fetch("""
            SELECT r.rolname, r.rolsuper, r.rolinherit, r.rolcreaterole,
                   r.rolcreatedb, r.rolcanlogin,
                   ARRAY(SELECT b.rolname FROM pg_catalog.pg_auth_members m
                         JOIN pg_catalog.pg_roles b ON m.roleid = b.oid
                         WHERE m.member = r.oid) as member_of
            FROM pg_catalog.pg_roles r
            WHERE r.rolname NOT LIKE 'pg_%'
            ORDER BY r.rolname
        """)
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def _get_conn(tenant_db: TenantDatabase):
    # Get password from Secrets Manager (simplified here)
    from app.config import settings
    client = boto3.client('secretsmanager', region_name=settings.aws_region)
    password = client.get_secret_value(
        SecretId=f"dbprovision/{tenant_db.id}/password"
    )['SecretString']
    
    return await asyncpg.connect(
        host=tenant_db.db_host, port=tenant_db.db_port,
        database=tenant_db.db_name, user=tenant_db.db_username,
        password=password
    )