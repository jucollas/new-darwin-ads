"""Dev Auth Service — lightweight JWT auth for development only."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.config import settings

app = FastAPI(title=settings.SERVICE_NAME, version="1.0.0")

security = HTTPBearer()

# ---------------------------------------------------------------------------
# In-memory user store + JSON persistence
# ---------------------------------------------------------------------------
USERS: dict[str, dict] = {}  # keyed by user id
DATA_FILE = Path(settings.DATA_DIR) / "users.json"


def _load_users() -> None:
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text())
            for u in data:
                USERS[u["id"]] = u
        except Exception:
            pass


def _save_users() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(list(USERS.values()), indent=2))


def _find_by_email(email: str) -> dict | None:
    for u in USERS.values():
        if u["email"] == email:
            return u
    return None


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"],
        "roles": ["user"],
        "iss": settings.JWT_ISSUER,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _user_response(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "whatsapp": user.get("whatsapp"),
        "avatar_url": user.get("avatar_url"),
    }


# ---------------------------------------------------------------------------
# Startup: load persisted users + seed default dev user
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    _load_users()
    if not _find_by_email("dev@adgen.ai"):
        dev_user = {
            "id": str(uuid.uuid4()),
            "email": "dev@adgen.ai",
            "password": _hash_password("dev123456"),
            "name": "Dev User",
            "whatsapp": None,
            "avatar_url": None,
        }
        USERS[dev_user["id"]] = dev_user
        _save_users()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
        )
        user_id = payload.get("sub")
        if not user_id or user_id not in USERS:
            raise HTTPException(status_code=401, detail="Invalid token")
        return USERS[user_id]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    name: str | None = None
    whatsapp: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/auth/register")
async def register(body: RegisterRequest):
    if _find_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = {
        "id": str(uuid.uuid4()),
        "email": body.email,
        "password": _hash_password(body.password),
        "name": body.name,
        "whatsapp": None,
        "avatar_url": None,
    }
    USERS[user["id"]] = user
    _save_users()
    return {"access_token": _create_token(user), "user": _user_response(user)}


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    user = _find_by_email(body.email)
    if not user or not _check_password(body.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": _create_token(user), "user": _user_response(user)}


@app.get("/api/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return _user_response(user)


@app.patch("/api/auth/profile")
async def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    if body.name is not None:
        user["name"] = body.name
    if body.whatsapp is not None:
        user["whatsapp"] = body.whatsapp
    _save_users()
    return _user_response(user)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
