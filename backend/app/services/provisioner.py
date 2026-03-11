import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import update, select

from app.models.tenant import TenantDatabase, DatabaseStatus, TIER_CONFIG
from app.infrastructure.terraform_executor import TerraformExecutor
from app.config import settings

log = logging.getLogger(__name__)


def get_fresh_session():
    """
    Create a completely fresh engine and session for use inside
    Celery tasks which run in their own event loop. Never reuse
    the module-level engine across loop boundaries.
    """
    engine = create_async_engine(
        settings.mgmt_db_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


class ProvisioningService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tf = TerraformExecutor()

    async def provision_database(self, tenant: TenantDatabase) -> TenantDatabase:
        log.info(f"Starting provisioning tenant_id={tenant.tenant_id} env={tenant.environment}")

        try:
            await self._update_status(
                tenant.id, DatabaseStatus.PROVISIONING,
                "Initializing infrastructure..."
            )

            tier_config = TIER_CONFIG[tenant.tier]
            workspace = f"tenant-{tenant.tenant_id}-{tenant.environment}"

            tf_vars = {
                "tenant_id":          tenant.tenant_id,
                "environment":        tenant.environment,
                "db_identifier":      tenant.db_identifier,
                "db_name":            tenant.db_name,
                "db_username":        tenant.db_username,
                "instance_class":     tier_config["instance_class"],
                "allocated_storage":  str(tier_config["storage"]),
                "aws_region":         tenant.aws_region,
                "multi_az":           str(tenant.multi_az).lower(),
                "deletion_protection":"false",
                "rds_subnet_group":   settings.rds_subnet_group,
                "rds_security_group_id": settings.rds_security_group_id,
                "backups_bucket":     settings.backup_s3_bucket,
            }

            await self._update_status(
                tenant.id, DatabaseStatus.PROVISIONING,
                "Running Terraform — this takes 4-6 minutes..."
            )

            log.info(f"Running terraform apply workspace={workspace}")
            outputs = await self.tf.apply(workspace, tf_vars)

            log.info(f"Terraform complete outputs={outputs}")

            await self.db.execute(
                update(TenantDatabase)
                .where(TenantDatabase.id == tenant.id)
                .values(
                    db_host=outputs.get("db_endpoint"),
                    db_port=int(outputs.get("db_port", 5432)),
                    rds_arn=outputs.get("db_arn"),
                    terraform_workspace=workspace,
                    status=DatabaseStatus.ACTIVE,
                    status_message="Database provisioned successfully",
                    monthly_cost_estimate=tier_config["cost_per_hour"] * 730,
                    updated_at=datetime.utcnow()
                )
            )
            await self.db.commit()

            log.info(f"Provisioning complete tenant_id={tenant.tenant_id}")
            return tenant

        except Exception as e:
            log.error(f"Provisioning failed tenant_id={tenant.tenant_id} error={str(e)}")
            await self._update_status(tenant.id, DatabaseStatus.ERROR, str(e))
            raise

    async def deprovision_database(self, tenant: TenantDatabase, force: bool = False):
        if tenant.environment == "prod" and not force:
            raise ValueError("Cannot deprovision production database without force=True")

        if tenant.terraform_workspace:
            await self.tf.destroy(tenant.terraform_workspace)

        await self._update_status(
            tenant.id, DatabaseStatus.DEPROVISIONED,
            "Database deprovisioned"
        )

    async def _update_status(self, tenant_id: str, status: DatabaseStatus, message: str):
        await self.db.execute(
            update(TenantDatabase)
            .where(TenantDatabase.id == tenant_id)
            .values(
                status=status,
                status_message=message,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()

    async def _get_db_password(self, tenant_id: str) -> str:
        import boto3
        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        response = client.get_secret_value(
            SecretId=f"dbprovision/{tenant_id}/password"
        )
        return response["SecretString"]