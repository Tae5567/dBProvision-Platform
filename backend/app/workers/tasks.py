import asyncio
import logging
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


def run_async(coro):
    """
    Run an async coroutine safely inside a Celery task.
    Always creates a fresh event loop to avoid loop-boundary issues
    with SQLAlchemy asyncpg connection pools.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # Close all async generators and shutdown executor
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="tasks.provision_database_task"
)
def provision_database_task(self, tenant_db_id: str):
    async def _run():
        # Import here to avoid module level engine creation
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import select
        from app.models.tenant import TenantDatabase
        from app.services.provisioner import ProvisioningService
        from app.config import settings

        # Fresh engine per task: never share across event loops
        engine = create_async_engine(settings.mgmt_db_url, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with session_factory() as db:
                result = await db.execute(
                    select(TenantDatabase).where(TenantDatabase.id == tenant_db_id)
                )
                tenant_db = result.scalar_one_or_none()
                if not tenant_db:
                    log.error(f"TenantDatabase {tenant_db_id} not found")
                    return

                service = ProvisioningService(db)
                await service.provision_database(tenant_db)
        finally:
            await engine.dispose()

    try:
        run_async(_run())
    except Exception as exc:
        log.error(f"Provisioning task failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=2,
    name="tasks.run_bulk_migration_task"
)
def run_bulk_migration_task(self, job_id: str, concurrency: int = 10):
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import select
        from app.models.migration import BulkMigrationJob, Migration
        from app.models.tenant import TenantDatabase, DatabaseStatus
        from app.services.migration_runner import MigrationRunner
        from app.config import settings

        engine = create_async_engine(settings.mgmt_db_url, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with session_factory() as db:
                job = await db.get(BulkMigrationJob, job_id)
                if not job:
                    log.error(f"BulkMigrationJob {job_id} not found")
                    return

                migration = await db.get(Migration, job.migration_id)

                query = select(TenantDatabase).where(
                    TenantDatabase.status == DatabaseStatus.ACTIVE
                )
                if job.target_env != "all":
                    query = query.where(TenantDatabase.environment == job.target_env)
                if job.target_tenant_ids:
                    query = query.where(
                        TenantDatabase.tenant_id.in_(job.target_tenant_ids)
                    )

                result = await db.execute(query)
                tenant_dbs = result.scalars().all()

                runner = MigrationRunner(db)
                await runner.run_bulk_migration(job, migration, tenant_dbs, concurrency)
        finally:
            await engine.dispose()

    try:
        run_async(_run())
    except Exception as exc:
        log.error(f"Bulk migration task failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.create_backup_task"
)
def create_backup_task(self, db_id: str, backup_type: str, created_by: str):
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from app.models.tenant import TenantDatabase
        from app.models.backup import BackupType
        from app.services.backup_manager import BackupManager
        from app.config import settings

        engine = create_async_engine(settings.mgmt_db_url, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with session_factory() as db:
                tenant_db = await db.get(TenantDatabase, db_id)
                if not tenant_db:
                    log.error(f"TenantDatabase {db_id} not found")
                    return

                manager = BackupManager(db)
                await manager.create_snapshot(
                    tenant_db,
                    BackupType(backup_type),
                    created_by
                )
        finally:
            await engine.dispose()

    try:
        run_async(_run())
    except Exception as exc:
        log.error(f"Backup task failed: {exc}")
        raise self.retry(exc=exc)