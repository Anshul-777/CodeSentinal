"""
CodeSentinel — Auth API
Registration, login, token refresh, logout, profile, tour state.
Test account is seeded by a separate CLI command — NOT exposed here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    UserRole,
    create_access_token,
    create_refresh_token,
    decode_token,
    encryption,
    generate_api_key,
    get_current_user,
    hash_api_key,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.audit import AuditLog
from app.models.organization import Organization, OrganizationMember
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.auth")


# ── Schemas ────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    job_title: str = Field(min_length=2, max_length=255)
    company: str = Field(min_length=2, max_length=255)
    github_username: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=50)
    organization_name: str = Field(min_length=2, max_length=255)
    use_case: str = Field(min_length=10, max_length=500)
    # Agree to terms is required
    agree_to_terms: bool

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        ok, msg = validate_password_strength(v)
        if not ok:
            raise ValueError(msg)
        return v

    @field_validator("agree_to_terms")
    @classmethod
    def must_agree(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must agree to the Terms of Service to register.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class TourUpdateRequest(BaseModel):
    tour_completed: Optional[bool] = None
    tour_step: Optional[int] = None


# ── Helpers ────────────────────────────────────────────────────────────────────
def _user_to_dict(user: User, org: Optional[Organization] = None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "job_title": user.job_title,
        "company": user.company,
        "github_username": user.github_username,
        "avatar_url": user.avatar_url,
        "is_test_user": user.is_test_user,
        "tour_completed": user.tour_completed,
        "tour_step": user.tour_step,
        "notify_email": user.notify_email,
        "notify_slack": user.notify_slack,
        "created_at": user.created_at.isoformat(),
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "plan": org.plan,
        } if org else None,
    }


async def _record_audit(
    db: AsyncSession,
    action: str,
    user: Optional[User],
    request: Request,
    result: str = "success",
    details: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    log_entry = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user.id if user else None,
        actor_email=user.email if user else None,
        action=action,
        resource_type="auth",
        result=result,
        details=details,
        error_message=error,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
        created_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)


# ── Routes ─────────────────────────────────────────────────────────────────────
@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user with organization creation."""
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    # Generate org slug from company name
    from slugify import slugify
    base_slug = slugify(payload.organization_name)[:80]
    slug = base_slug
    suffix = 1
    while True:
        exists = await db.execute(select(Organization).where(Organization.slug == slug))
        if not exists.scalar_one_or_none():
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    # Create user
    user = User(
        id=user_id,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        job_title=payload.job_title,
        company=payload.company,
        github_username=payload.github_username,
        phone=payload.phone,
        primary_org_id=None,
        is_active=True,
        is_verified=False,
        is_test_user=False,
        tour_completed=False,
        tour_step=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    # Create organization after user exists to satisfy owner FK
    org = Organization(
        id=org_id,
        name=payload.organization_name,
        slug=slug,
        owner_id=user_id,
        plan="free",
        compliance_profiles=["soc2", "owasp"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(org)

    # Link user to primary organization
    user.primary_org_id = org_id

    # Create owner membership
    membership = OrganizationMember(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user_id,
        role=UserRole.OWNER.value,
        accepted_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(membership)

    await _record_audit(db, "user.registered", user, request, details={"org": slug, "use_case": payload.use_case[:100]})
    await db.commit()

    # Issue tokens
    access_token = create_access_token(user_id, extra={"role": UserRole.OWNER.value, "org_id": org_id})
    refresh_token = create_refresh_token(user_id)

    log.info("New user registered", user_id=user_id, email=payload.email, org=slug)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
        user=_user_to_dict(user, org),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return JWT tokens."""
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        await _record_audit(
            db, "user.login_failed", None, request,
            result="failure", error="Invalid credentials",
            details={"email": payload.email.lower()},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    # Load org
    org = None
    if user.primary_org_id:
        org_result = await db.execute(select(Organization).where(Organization.id == user.primary_org_id))
        org = org_result.scalar_one_or_none()

    # Get user role in org
    role = UserRole.VIEWER.value
    if org:
        mem_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == user.id,
            )
        )
        membership = mem_result.scalar_one_or_none()
        if membership:
            role = membership.role

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = request.client.host if request.client else None

    await _record_audit(db, "user.login", user, request)
    await db.commit()

    access_token = create_access_token(user.id, extra={"role": role, "org_id": str(org.id) if org else None})
    refresh_token = create_refresh_token(user.id)

    log.info("User logged in", user_id=user.id, email=user.email, is_test=user.is_test_user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
        user=_user_to_dict(user, org),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access token."""
    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    user_id = decoded.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated.")

    # Load org
    org = None
    role = UserRole.VIEWER.value
    if user.primary_org_id:
        org_result = await db.execute(select(Organization).where(Organization.id == user.primary_org_id))
        org = org_result.scalar_one_or_none()
        if org:
            mem_result = await db.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.user_id == user.id,
                )
            )
            membership = mem_result.scalar_one_or_none()
            if membership:
                role = membership.role

    access_token = create_access_token(user.id, extra={"role": role, "org_id": str(org.id) if org else None})
    new_refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=30 * 60,
        user=_user_to_dict(user, org),
    )


@router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get current authenticated user's profile."""
    org = None
    if current_user.primary_org_id:
        result = await db.execute(select(Organization).where(Organization.id == current_user.primary_org_id))
        org = result.scalar_one_or_none()
    return _user_to_dict(current_user, org)


@router.patch("/auth/tour")
async def update_tour_state(
    payload: TourUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the product tour state for the current user."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    if payload.tour_completed is not None:
        user.tour_completed = payload.tour_completed
    if payload.tour_step is not None:
        user.tour_step = payload.tour_step
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"tour_completed": user.tour_completed, "tour_step": user.tour_step}


@router.post("/auth/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log out and record in audit log."""
    await _record_audit(db, "user.logout", current_user, request)
    await db.commit()
    return {"message": "Logged out successfully."}


@router.post("/auth/generate-api-key")
async def generate_new_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key. Returns the raw key ONCE — store it immediately."""
    raw_key = generate_api_key()
    hashed = hash_api_key(raw_key)
    prefix = raw_key[:10]

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    user.api_key_hash = hashed
    user.api_key_prefix = prefix
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "api_key": raw_key,
        "prefix": prefix,
        "message": "Store this key now — it will not be shown again.",
    }
