import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from app.core.config import settings

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    user_id: str, email: str, role: str, team_id: str | None
) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "team_id": team_id,
        "exp": datetime.now(timezone.utc)
        + timedelta(days=settings.access_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
