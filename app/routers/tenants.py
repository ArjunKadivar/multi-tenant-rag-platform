from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Tenant
from app.schemas import TenantCreate, TenantOut
from app.security import generate_api_key, hash_api_key, require_admin

router = APIRouter(prefix="/tenants", tags=["tenants"], dependencies=[Depends(require_admin)])


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)) -> TenantOut:
    raw_key = generate_api_key()
    tenant = Tenant(name=payload.name, plan=payload.plan, api_key_hash=hash_api_key(raw_key))
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    # The raw key is returned exactly once — it is never retrievable again,
    # matching how GitHub/Stripe personal access tokens behave.
    return TenantOut(id=tenant.id, name=tenant.name, plan=tenant.plan, api_key=raw_key, created_at=tenant.created_at)
