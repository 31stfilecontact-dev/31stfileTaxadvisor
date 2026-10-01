from fastapi import APIRouter

router = APIRouter()


@router.get("/api/healthz", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}