import boto3
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup import Backup, BackupType, BackupStatus
from app.models.tenant import TenantDatabase
from app.config import settings

log = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rds = boto3.client('rds', region_name=settings.aws_region)
        self.s3 = boto3.client('s3', region_name=settings.aws_region)

    async def create_snapshot(
        self,
        tenant_db: TenantDatabase,
        backup_type: BackupType = BackupType.MANUAL,
        created_by: str = "system"
    ) -> Backup:
        """Create an RDS snapshot backup."""
        
        snapshot_id = f"{tenant_db.db_identifier}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        backup = Backup(
            tenant_db_id=tenant_db.id,
            backup_type=backup_type,
            status=BackupStatus.IN_PROGRESS,
            rds_snapshot_id=snapshot_id,
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=settings.backup_retention_days),
            created_by=created_by
        )
        self.db.add(backup)
        await self.db.commit()
        
        try:
            response = self.rds.create_db_snapshot(
                DBSnapshotIdentifier=snapshot_id,
                DBInstanceIdentifier=tenant_db.db_identifier,
                Tags=[
                    {"Key": "TenantId", "Value": tenant_db.tenant_id},
                    {"Key": "Environment", "Value": tenant_db.environment},
                    {"Key": "BackupType", "Value": backup_type.value},
                    {"Key": "ManagedBy", "Value": "DBProvision"},
                ]
            )
            
            backup.rds_snapshot_arn = response['DBSnapshot']['DBSnapshotArn']
            backup.status = BackupStatus.IN_PROGRESS
            await self.db.commit()
            
            # Wait for snapshot completion (in production, use event-driven approach)
            waiter = self.rds.get_waiter('db_snapshot_completed')
            waiter.wait(DBSnapshotIdentifier=snapshot_id)
            
            snapshot = self.rds.describe_db_snapshots(
                DBSnapshotIdentifier=snapshot_id
            )['DBSnapshots'][0]
            
            backup.status = BackupStatus.COMPLETED
            backup.size_bytes = snapshot.get('AllocatedStorage', 0) * 1024 * 1024 * 1024
            backup.completed_at = datetime.utcnow()
            backup.duration_seconds = int(
                (backup.completed_at - backup.started_at).total_seconds()
            )
            
            await self.db.commit()
            log.info(f"Snapshot created snapshot_id={snapshot_id} tenant={tenant_db.tenant_id}")
            
            return backup
            
        except Exception as e:
            log.error(f"Backup failed error={str(e)} tenant={tenant_db.tenant_id}")
            backup.status = BackupStatus.FAILED
            backup.error_message = str(e)
            backup.completed_at = datetime.utcnow()
            await self.db.commit()
            raise

    async def restore_from_snapshot(
        self,
        backup: Backup,
        tenant_db: TenantDatabase,
        target_identifier: str
    ) -> str:
        """Restore database from a snapshot."""
        
        log.info(f"Starting restore snapshot={backup.rds_snapshot_id} target={target_identifier}")

        
        self.rds.restore_db_instance_from_db_snapshot(
            DBInstanceIdentifier=target_identifier,
            DBSnapshotIdentifier=backup.rds_snapshot_id,
            DBInstanceClass=tenant_db.tier,
            MultiAZ=tenant_db.multi_az,
            PubliclyAccessible=False,
            Tags=[
                {"Key": "RestoredFrom", "Value": backup.rds_snapshot_id},
                {"Key": "TenantId", "Value": tenant_db.tenant_id},
            ]
        )
        
        waiter = self.rds.get_waiter('db_instance_available')
        waiter.wait(DBInstanceIdentifier=target_identifier)
        
        return target_identifier

    async def delete_expired_backups(self):
        """Clean up expired snapshots and S3 files."""
        from sqlalchemy import select, and_
        from datetime import datetime
        
        result = await self.db.execute(
            select(Backup).where(
                and_(
                    Backup.status == BackupStatus.COMPLETED,
                    Backup.expires_at < datetime.utcnow()
                )
            )
        )
        expired = result.scalars().all()
        
        for backup in expired:
            try:
                if backup.rds_snapshot_id:
                    self.rds.delete_db_snapshot(
                        DBSnapshotIdentifier=backup.rds_snapshot_id
                    )
                backup.status = BackupStatus.EXPIRED
            except Exception as e:
                log.error(f"Failed to delete backup backup_id={backup.id} error={str(e)}")
        
        await self.db.commit()
        return len(expired)