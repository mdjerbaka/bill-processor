"""Authentication & user management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.models import AppSetting, Job, QBOToken, User
from app.schemas.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    SetupRequest,
    SetupStatusResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: validate JWT and return the current user."""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


@router.post("/setup", response_model=TokenResponse)
async def initial_setup(req: SetupRequest, db: AsyncSession = Depends(get_db)):
    """First-time setup: create the initial user account."""
    # Check if any user already exists
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar()
    if count > 0:
        raise HTTPException(status_code=400, detail="Setup already completed")

    user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    await db.flush()

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login with username and password."""
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token)


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(req.new_password)
    await db.flush()
    return {"message": "Password changed successfully"}


@router.get("/setup-status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db)):
    """Check what setup steps have been completed."""
    # Has user?
    result = await db.execute(select(func.count(User.id)))
    has_user = result.scalar() > 0

    # Has email config?
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "imap_host").limit(1)
    )
    has_email = result.scalar_one_or_none() is not None

    # Has QBO connection?
    result = await db.execute(select(func.count(QBOToken.id)))
    has_qbo = result.scalar() > 0

    # Has jobs?
    result = await db.execute(select(func.count(Job.id)))
    has_jobs = result.scalar() > 0

    is_complete = has_user and has_email

    return SetupStatusResponse(
        is_setup_complete=is_complete,
        has_user=has_user,
        has_email_config=has_email,
        has_qbo_connection=has_qbo,
        has_jobs=has_jobs,
    )
