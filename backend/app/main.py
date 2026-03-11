from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routers import provisioning, migrations, backups, monitoring, access
from app.models.database import engine, Base
from app.routers import provisioning, migrations, backups, monitoring, access, costs
from prometheus_fastapi_instrumentator import Instrumentator


log = logging.getLogger(__name__)

app = FastAPI(
    title="DBProvision API",
    description="Multi-Tenant Database Provisioning & Management System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://dbprovision.internal"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(provisioning.router)
app.include_router(migrations.router)
app.include_router(backups.router)
app.include_router(monitoring.router)
app.include_router(access.router)
app.include_router(costs.router)

@app.on_event("startup")
async def startup():
    log.info("DBProvision API starting up")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "dbprovision-api"}


Instrumentator().instrument(app).expose(app)