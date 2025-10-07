from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import os, jwt
from passlib.hash import argon2, bcrypt
from .db import SessionLocal
from .models import User


# --------------------------------------------------------------------
# Environment & Security Configuration
# --------------------------------------------------------------------

# Load environment variables from .env

load_dotenv()

# FastAPI security dependency for Bearer tokens
security = HTTPBearer(auto_error=True)

# JWT configuration
JWT_SECRET = os.getenv("RAG_JWT_SECRET", "dev-secret")
JWT_ALG = "HS256"
TOKEN_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "60"))

# --------------------------------------------------------------------
# Database Session Dependency
# --------------------------------------------------------------------
def get_db():
    """
    Provide a database session to FastAPI dependencies.

    This function yields a SQLAlchemy session (`SessionLocal`) and ensures
    it is properly closed after use. It is designed to be used as a FastAPI dependency.

    Yields:
        Session: An active SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# --------------------------------------------------------------------
# Password Hashing Utilities
# --------------------------------------------------------------------
def hash_password(pw: str) -> str:
    """
    Hash a plaintext password using Argon2 or bcrypt.

    The default hashing algorithm is Argon2 (stronger, memory-hard).
    You can override this by setting the `PASSWORD_HASHER` environment variable.

    Args:
        pw (str): The plaintext password to hash.

    Returns:
        str: The hashed password string.
    """
    prefer = os.getenv("PASSWORD_HASHER", "argon2")
    return argon2.hash(pw) if prefer == "argon2" else bcrypt.hash(pw)


def verify_password(pw: str, ph: str) -> bool:
    """
    Verify that a plaintext password matches a stored hash.

    Supports both Argon2 and bcrypt hash formats. Automatically detects which
    algorithm to use based on the stored hash prefix.

    Args:
        pw (str): The plaintext password to check.
        ph (str): The stored password hash.

    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        if ph.startswith("$argon2"):
            return argon2.verify(pw, ph)
        return bcrypt.verify(pw, ph)
    except Exception:
        return False

# --------------------------------------------------------------------
# JWT Token Utilities
# --------------------------------------------------------------------
def create_jwt(user_id: int) -> str:
    """
    Generate a signed JWT access token for a user.

    The token includes:
      - `sub`: user ID (subject)
      - `iat`: issued-at timestamp
      - `exp`: expiration timestamp (based on TOKEN_TTL_MIN)

    Args:
        user_id (int): The ID of the authenticated user.

    Returns:
        str: The encoded JWT access token.
    """
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=TOKEN_TTL_MIN)).timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    """
    Retrieve the current authenticated user based on a JWT Bearer token.

    This dependency decodes and validates the JWT, verifies that the user exists,
    and returns the corresponding `User` ORM object.

    Args:
        creds (HTTPAuthorizationCredentials): Bearer token credentials extracted by FastAPI.
        db (Session): SQLAlchemy database session.

    Raises:
        HTTPException: 
            - 401 if the token is invalid or expired.
            - 401 if the user does not exist.

    Returns:
        User: The authenticated user instance.
    """
    token = creds.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
