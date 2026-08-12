import os
import base64
import hashlib
from datetime import datetime, timedelta
import bcrypt
from cryptography.fernet import Fernet
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditLog
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_gas kit_shop_management_system")
fernet_key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
fernet = Fernet(fernet_key)

SESSION_COOKIE_NAME = "session_token"
SESSION_DURATION_HOURS = 2
REMEMBER_DURATION_HOURS = 24 * 14  # 14 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_session_token(user_id: int, remember: bool = False) -> str:
    hours = REMEMBER_DURATION_HOURS if remember else SESSION_DURATION_HOURS
    expires = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
    data = f"{user_id}:{expires}"
    return fernet.encrypt(data.encode()).decode()


def session_max_age(remember: bool = False) -> int:
    hours = REMEMBER_DURATION_HOURS if remember else SESSION_DURATION_HOURS
    return hours * 3600


def get_user_id_from_token(token: str):
    try:
        decrypted = fernet.decrypt(token.encode()).decode()
        user_id_str, expires_str = decrypted.split(":", 1)
        expires = datetime.fromisoformat(expires_str)
        if datetime.utcnow() > expires:
            return None
        return int(user_id_str)
    except Exception:
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != "Active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    return user


def get_optional_current_user(request: Request, db: Session = Depends(get_db)):
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def log_audit(db: Session, user_id, action: str, details: str = None):
    log_entry = AuditLog(user_id=user_id, action=action, details=details)
    db.add(log_entry)
    db.commit()
