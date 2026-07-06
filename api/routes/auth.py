import json
import logging
import secrets
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from time import time
from typing import Annotated

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.auth import (
    AuthUrlResponse,
    UserResponse,
)
from config import settings
from db.models import User
from db.session import get_db
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
JWKS_TTL = 86400

_google_jwks: dict | None = None
_google_jwks_fetched: float = 0


async def _get_google_public_key(kid: str):
    global _google_jwks, _google_jwks_fetched
    now = time()
    if not _google_jwks or (now - _google_jwks_fetched) > JWKS_TTL:
        async with httpx.AsyncClient() as client:
            resp = await client.get(GOOGLE_JWKS_URL)
            _google_jwks = resp.json()
            _google_jwks_fetched = now
    for key in _google_jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    raise ValueError(f"Google public key with kid={kid} not found")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire, "auth_method": "google"})
    return jwt.encode(to_encode, settings.jwt_auth_secret, algorithm="HS256")


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ] = None,
) -> User:
    token = None
    if credentials is not None:
        token = credentials.credentials
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer ") :]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, settings.jwt_auth_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or user.deleted:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/google/login", response_model=AuthUrlResponse)
async def google_login():
    state = secrets.token_urlsafe(32)
    state_token = jwt.encode(
        {
            "state": state,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.jwt_auth_secret,
        algorithm="HS256",
    )

    params = {
        "client_id": settings.client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state_token,
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str,
    state: str,
    error: str | None = None,
):
    if error:
        raise HTTPException(status_code=400, detail=f"Google auth error: {error}")

    try:
        jwt.decode(state, settings.jwt_auth_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.client_id,
                "client_secret": settings.client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed: {token_resp.text}",
        )

    tokens = token_resp.json()
    id_token_str = tokens.get("id_token")
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not id_token_str:
        raise HTTPException(status_code=400, detail="No ID token received")

    try:
        header = jwt.get_unverified_header(id_token_str)
        kid = header.get("kid")
        if not kid:
            raise ValueError("No kid in ID token header")
        key = await _get_google_public_key(kid)
        id_info = jwt.decode(
            id_token_str,
            key,
            algorithms=["RS256"],
            audience=settings.client_id,
            issuer=["accounts.google.com", "https://accounts.google.com"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"ID token verification failed: {e}"
        )

    google_sub = id_info["sub"]
    email = id_info.get("email", "")
    name = id_info.get("name", email.split("@")[0] if email else "User")
    avatar = id_info.get("picture", "")

    result = await db.execute(
        select(User).where((User.google_id == google_sub) | (User.email == email))
    )
    user = result.scalar_one_or_none()

    if user:
        user.google_id = google_sub
        user.avatar_url = avatar or user.avatar_url
        user.full_name = name
        if access_token:
            user.google_access_token = access_token
        if refresh_token:
            user.google_refresh_token = refresh_token
        if email == settings.admin_email:
            user.role = "admin"
    else:
        role = "admin" if email == settings.admin_email else "user"
        user = User(
            id=str(uuid.uuid4()),
            username=email.split("@")[0] if email else google_sub,
            email=email,
            full_name=name,
            role=role,
            google_id=google_sub,
            avatar_url=avatar,
            google_access_token=access_token,
            google_refresh_token=refresh_token,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    jwt_token = create_access_token({"sub": user.id})

    return RedirectResponse(
        url=f"{settings.frontend_url}/oauth/callback#token={jwt_token}",
        status_code=302,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        role=current_user.role,
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out"}


async def ensure_admin_user(db: AsyncSession):
    result = await db.execute(select(User).where(User.email == settings.admin_email))
    user = result.scalar_one_or_none()
    if user:
        if user.role != "admin":
            user.role = "admin"
            await db.commit()
        return
    admin = User(
        id=str(uuid.uuid4()),
        username=settings.admin_email.split("@")[0],
        email=settings.admin_email,
        full_name="Admin",
        role="admin",
    )
    db.add(admin)
    await db.commit()
    logger.info("Admin user created with email: %s", settings.admin_email)
