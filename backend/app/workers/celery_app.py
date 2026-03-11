from celery import Celery
from app.config import settings

celery_app = Celery(
    "dbprovision",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_routes={
        "app.workers.tasks.provision_database_task": {"queue": "provisioning"},
        "app.workers.tasks.run_bulk_migration_task": {"queue": "migrations"},
        "app.workers.tasks.create_backup_task": {"queue": "backups"},
    }
)