"""
routers/auth.py — JWT authentication endpoints
"""

import os
import time
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from db.database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ─── Config ───────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("JWT_SECRET", "changeme-insecure-default")
ALGORITHM    = "HS256"
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ─── Models ───────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    is_admin: bool
    expires_in: int  # seconds


class UserInfo(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: float
    last_login: float | None


# ─── Helpers ──────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(username: str, is_admin: bool) -> str:
    expire = datetime.utcnow() + timedelta(hours=EXPIRE_HOURS)
    payload = {
        "sub": username,
        "is_admin": is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency: decode JWT and return user payload."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
        return {"username": username, "is_admin": payload.get("is_admin", False)}
    except JWTError:
        raise credentials_exception


def require_admin(user=Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    return user


def ensure_admin_user():
    """Create default admin user on startup if not exists."""
    admin_name = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "admin")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM auditvisual_users WHERE username=?", (admin_name,)
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO auditvisual_users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                (admin_name, hash_password(admin_pass))
            )
            conn.commit()
            logger.info(f"Created default admin user: {admin_name}")
    finally:
        conn.close()


# ─── Endpoints ────────────────────────────────────────────────────────────────
@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM auditvisual_users WHERE username=?", (form.username,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not verify_password(form.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Update last_login
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE auditvisual_users SET last_login=? WHERE username=?",
            (time.time(), form.username)
        )
        conn.commit()
    finally:
        conn.close()

    token = create_token(form.username, bool(row["is_admin"]))
    return Token(
        access_token=token,
        token_type="bearer",
        username=form.username,
        is_admin=bool(row["is_admin"]),
        expires_in=EXPIRE_HOURS * 3600,
    )


@router.get("/me", response_model=UserInfo)
def me(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM auditvisual_users WHERE username=?", (user["username"],)
        ).fetchone()
        if not row:
            raise HTTPException(404, "User not found")
        return UserInfo(**dict(row))
    finally:
        conn.close()


@router.get("/users", response_model=list[UserInfo])
def list_users(admin=Depends(require_admin)):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM auditvisual_users ORDER BY created_at").fetchall()
        return [UserInfo(**dict(r)) for r in rows]
    finally:
        conn.close()


@router.post("/users")
def create_user(body: dict, admin=Depends(require_admin)):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    is_admin = body.get("is_admin", False)

    if not username or not password:
        raise HTTPException(400, "username and password required")

    conn = get_connection()
    try:
        try:
            conn.execute(
                "INSERT INTO auditvisual_users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                (username, hash_password(password), int(is_admin))
            )
            conn.commit()
        except Exception:
            raise HTTPException(409, "Username already exists")
        return {"message": f"User {username} created"}
    finally:
        conn.close()


@router.delete("/users/{username}")
def delete_user(username: str, admin=Depends(require_admin)):
    if username == admin["username"]:
        raise HTTPException(400, "Cannot delete yourself")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM auditvisual_users WHERE username=?", (username,))
        conn.commit()
        return {"message": f"User {username} deleted"}
    finally:
        conn.close()


@router.post("/users/{username}/password")
def change_password(username: str, body: dict, user=Depends(get_current_user)):
    # Admin can change any password; regular user can only change own
    if not user["is_admin"] and user["username"] != username:
        raise HTTPException(403, "Forbidden")

    new_pass = body.get("password", "")
    if len(new_pass) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE auditvisual_users SET password_hash=? WHERE username=?",
            (hash_password(new_pass), username)
        )
        conn.commit()
        return {"message": "Password changed"}
    finally:
        conn.close()
