from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db import get_db

router = APIRouter()


@router.get("/api/healthz", tags=["health"])
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database readiness check failed.",
        ) from exc
    return {"status": "healthy"}