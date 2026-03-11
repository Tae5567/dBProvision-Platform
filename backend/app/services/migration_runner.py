import asyncio
import hashlib
import logging
import traceback
from datetime import datetime
from typing import List, Optional
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.migration import Migration, MigrationRun, MigrationStatus, BulkMigrationJob
from app.models.tenant import TenantDatabase, DatabaseStatus

log = logging.getLogger(__name__)

class MigrationRunner:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply_migration(
        self,
        migration: Migration,
        tenant_db: TenantDatabase,
        run_by: str = "system"
    ) -> MigrationRun:
        """Apply a single migration to a single database."""
        
        run = MigrationRun(
            migration_id=migration.id,
            tenant_db_id=tenant_db.id,
            status=MigrationStatus.RUNNING,
            started_at=datetime.utcnow(),
            run_by=run_by
        )
        self.db.add(run)
        await self.db.commit()
        
        start_time = datetime.utcnow()
        
        try:
            # Get connection
            conn = await self._get_connection(tenant_db)
            
            try:
                # Check if already applied
                existing = await conn.fetchrow(
                    "SELECT id FROM _schema_migrations WHERE version = $1",
                    migration.version
                )
                
                if existing:
                    log.info(f"Migration already applied migration={migration.name} tenant={tenant_db.tenant_id}")
                    run.status = MigrationStatus.COMPLETED
                    run.error_message = "Already applied"
                    return run

                # Apply in transaction
                async with conn.transaction():
                    await conn.execute(migration.up_sql)
                    
                    await conn.execute("""
                        INSERT INTO _schema_migrations (version, name, checksum, applied_by)
                        VALUES ($1, $2, $3, $4)
                    """, migration.version, migration.name, migration.checksum, run_by)
                
                elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
                run.status = MigrationStatus.COMPLETED
                run.execution_time_ms = int(elapsed)
                run.completed_at = datetime.utcnow()
                
                log.info(f"Migration applied migration={migration.name} tenant={tenant_db.tenant_id} duration_ms={elapsed}")
                
            finally:
                await conn.close()
                
        except Exception as e:
            full_error = traceback.format_exc()
            log.error(f"Migration failed migration={migration.name} tenant={tenant_db.tenant_id} error={str(e)} traceback={full_error}")
            run.status = MigrationStatus.FAILED
            run.error_message = full_error[:500]  # store traceback not just str(e)
            run.completed_at = datetime.utcnow()
        
        await self.db.commit()
        return run

    async def rollback_migration(
        self,
        migration: Migration,
        tenant_db: TenantDatabase
    ) -> MigrationRun:
        """Rollback a migration using down_sql."""
        
        if not migration.down_sql:
            raise ValueError(f"Migration {migration.name} has no rollback SQL")
        
        conn = await self._get_connection(tenant_db)
        try:
            async with conn.transaction():
                await conn.execute(migration.down_sql)
                await conn.execute(
                    "DELETE FROM _schema_migrations WHERE version = $1",
                    migration.version
                )
        finally:
            await conn.close()

    async def run_bulk_migration(
        self,
        job: BulkMigrationJob,
        migration: Migration,
        tenant_dbs: List[TenantDatabase],
        concurrency: int = 10
    ) -> BulkMigrationJob:
        """Apply migration to multiple databases with concurrency control."""
        
        job.total_databases = len(tenant_dbs)
        job.status = MigrationStatus.RUNNING
        job.started_at = datetime.utcnow()
        await self.db.commit()
        
        semaphore = asyncio.Semaphore(concurrency)
        results = {}
        
        async def run_one(tenant_db: TenantDatabase):
            async with semaphore:
                run = await self.apply_migration(migration, tenant_db)
                results[tenant_db.tenant_id] = {
                    "status": run.status,
                    "duration_ms": run.execution_time_ms,
                    "error": run.error_message
                }
                
                if run.status == MigrationStatus.COMPLETED:
                    job.completed += 1
                else:
                    job.failed += 1
                
                await self.db.commit()
        
        await asyncio.gather(*[run_one(db) for db in tenant_dbs])
        
        job.results = results
        job.status = (MigrationStatus.COMPLETED 
                      if job.failed == 0 
                      else MigrationStatus.FAILED)
        job.completed_at = datetime.utcnow()
        await self.db.commit()
        
        return job

    @staticmethod
    def compute_checksum(sql: str) -> str:
        return hashlib.sha256(sql.encode()).hexdigest()

    async def _get_connection(self, tenant_db: TenantDatabase):
        password = await self._get_password(tenant_db)
        return await asyncpg.connect(
            host=tenant_db.db_host,
            port=tenant_db.db_port,
            database=tenant_db.db_name,
            user=tenant_db.db_username,
            password=password,
            timeout=30,
            ssl="require"
        )

    async def _get_password(self, tenant_db: TenantDatabase) -> str:
        # Fetch from AWS Secrets Manager
        import boto3
        from app.config import settings
        client = boto3.client('secretsmanager', region_name=settings.aws_region)
        secret = client.get_secret_value(SecretId=f"dbprovision/{tenant_db.tenant_id}/password")
        return secret['SecretString']