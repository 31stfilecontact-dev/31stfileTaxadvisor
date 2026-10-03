from fastapi import APIRouter, Depends

from backend.auth import TeamMember, get_current_member
from backend.schemas import TeamSessionOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/session", response_model=TeamSessionOut)
def team_session(
    _member: TeamMember = Depends(get_current_member),
) -> TeamSessionOut:
    return TeamSessionOut(authenticated=True)