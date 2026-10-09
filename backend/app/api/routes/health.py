from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.schemas.api import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(session: DbSession) -> HealthOut:
    session.execute(text("SELECT 1"))
    return HealthOut(status="ok", database="ok")
