from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.models.database import get_db
from app.models.tenant import TenantDatabase, DatabaseStatus, TIER_CONFIG, DatabaseTier

router = APIRouter(prefix="/api/v1/costs", tags=["costs"])


class CostSummary(BaseModel):
    tenant_id: str
    tenant_name: str
    environment: str
    tier: str
    monthly_estimate: float
    daily_estimate: float
    hourly_rate: float


class FleetCostReport(BaseModel):
    total_monthly: float
    total_daily: float
    by_environment: dict
    by_team: dict
    by_tier: dict
    top_spenders: List[CostSummary]
    generated_at: str


@router.get("/summary", response_model=FleetCostReport)
async def get_fleet_cost_summary(db: AsyncSession = Depends(get_db)):
    """Fleet-wide cost breakdown by env, team, and tier."""

    result = await db.execute(
        select(TenantDatabase).where(
            TenantDatabase.status != DatabaseStatus.DEPROVISIONED
        )
    )
    databases = result.scalars().all()

    total_monthly = sum(d.monthly_cost_estimate for d in databases)
    total_daily = total_monthly / 30

    by_env: dict = {}
    by_team: dict = {}
    by_tier: dict = {}

    for d in databases:
        by_env[d.environment] = by_env.get(d.environment, 0) + d.monthly_cost_estimate
        team = d.team or "unassigned"
        by_team[team] = by_team.get(team, 0) + d.monthly_cost_estimate
        tier = d.tier.value if hasattr(d.tier, "value") else str(d.tier)
        by_tier[tier] = by_tier.get(tier, 0) + d.monthly_cost_estimate

    # Round all values
    by_env = {k: round(v, 2) for k, v in by_env.items()}
    by_team = {k: round(v, 2) for k, v in by_team.items()}
    by_tier = {k: round(v, 2) for k, v in by_tier.items()}

    # Top 10 spenders
    top = sorted(databases, key=lambda d: d.monthly_cost_estimate, reverse=True)[:10]
    top_spenders = [
        CostSummary(
            tenant_id=d.tenant_id,
            tenant_name=d.tenant_name,
            environment=d.environment,
            tier=d.tier.value if hasattr(d.tier, "value") else str(d.tier),
            monthly_estimate=round(d.monthly_cost_estimate, 2),
            daily_estimate=round(d.monthly_cost_estimate / 30, 4),
            hourly_rate=TIER_CONFIG[d.tier]["cost_per_hour"],
        )
        for d in top
    ]

    return FleetCostReport(
        total_monthly=round(total_monthly, 2),
        total_daily=round(total_daily, 4),
        by_environment=by_env,
        by_team=by_team,
        by_tier=by_tier,
        top_spenders=top_spenders,
        generated_at=datetime.utcnow().isoformat(),
    )


@router.get("/tenant/{tenant_id}")
async def get_tenant_cost(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Cost breakdown for a single tenant across all environments."""

    result = await db.execute(
        select(TenantDatabase).where(
            TenantDatabase.tenant_id == tenant_id,
            TenantDatabase.status != DatabaseStatus.DEPROVISIONED,
        )
    )
    databases = result.scalars().all()

    if not databases:
        raise HTTPException(404, f"No active databases found for tenant {tenant_id}")

    total_monthly = sum(d.monthly_cost_estimate for d in databases)

    return {
        "tenant_id": tenant_id,
        "tenant_name": databases[0].tenant_name,
        "total_monthly_estimate": round(total_monthly, 2),
        "total_annual_estimate": round(total_monthly * 12, 2),
        "databases": [
            {
                "id": d.id,
                "environment": d.environment,
                "tier": d.tier.value if hasattr(d.tier, "value") else str(d.tier),
                "monthly_estimate": round(d.monthly_cost_estimate, 2),
                "multi_az": d.multi_az,
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
            }
            for d in databases
        ],
    }


@router.get("/recommendations")
async def get_cost_recommendations(db: AsyncSession = Depends(get_db)):
    """
    Analyse usage patterns and suggest downsizing or rightsizing opportunities.
    In production this would use CloudWatch metrics; here we flag based on tier + env heuristics.
    """

    result = await db.execute(
        select(TenantDatabase).where(
            TenantDatabase.status == DatabaseStatus.ACTIVE
        )
    )
    databases = result.scalars().all()

    recommendations = []

    for d in databases:
        tier = d.tier.value if hasattr(d.tier, "value") else str(d.tier)

        # Dev databases running on medium+ are wasteful
        if d.environment == "dev" and tier in ("medium", "large", "xlarge"):
            savings = d.monthly_cost_estimate - TIER_CONFIG[DatabaseTier.SMALL]["cost_per_hour"] * 730
            recommendations.append({
                "tenant_id": d.tenant_id,
                "db_id": d.id,
                "environment": d.environment,
                "current_tier": tier,
                "suggested_tier": "small",
                "monthly_savings_estimate": round(savings, 2),
                "reason": "Dev environment running on oversized instance. Downsize to small.",
                "priority": "medium",
            })

        # Staging with multi-AZ is unusual and expensive
        if d.environment == "staging" and d.multi_az:
            savings = d.monthly_cost_estimate * 0.4  # Multi-AZ roughly doubles cost
            recommendations.append({
                "tenant_id": d.tenant_id,
                "db_id": d.id,
                "environment": d.environment,
                "current_tier": tier,
                "suggested_tier": tier,
                "monthly_savings_estimate": round(savings, 2),
                "reason": "Staging environment has Multi-AZ enabled. Disable for ~40% savings.",
                "priority": "low",
            })

        # Micro in production is a risk flag (not a cost saving, but operational)
        if d.environment == "prod" and tier == "micro":
            recommendations.append({
                "tenant_id": d.tenant_id,
                "db_id": d.id,
                "environment": d.environment,
                "current_tier": tier,
                "suggested_tier": "small",
                "monthly_savings_estimate": 0,
                "reason": "Production database on micro instance. Consider upgrading for reliability.",
                "priority": "high",
            })

    total_savings = sum(r["monthly_savings_estimate"] for r in recommendations)

    return {
        "recommendations": sorted(recommendations, key=lambda r: r["monthly_savings_estimate"], reverse=True),
        "total_potential_monthly_savings": round(total_savings, 2),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/projection")
async def get_cost_projection(
    months: int = 12,
    growth_rate_pct: float = 10.0,
    db: AsyncSession = Depends(get_db)
):
    """Project future costs assuming a monthly growth rate in database count."""

    result = await db.scalar(
        select(func.sum(TenantDatabase.monthly_cost_estimate)).where(
            TenantDatabase.status == DatabaseStatus.ACTIVE
        )
    )
    current_monthly = float(result or 0)

    growth = growth_rate_pct / 100
    projection = []
    for i in range(1, months + 1):
        projected = current_monthly * ((1 + growth) ** i)
        month_label = (datetime.utcnow() + timedelta(days=30 * i)).strftime("%Y-%m")
        projection.append({
            "month": month_label,
            "projected_monthly_cost": round(projected, 2),
            "projected_annual_run_rate": round(projected * 12, 2),
        })

    return {
        "current_monthly_cost": round(current_monthly, 2),
        "assumed_growth_rate_pct": growth_rate_pct,
        "projection": projection,
    }