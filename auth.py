"""
Authentication module for HelperGPT
Handles admin login, JWT tokens, and user verification
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
import logging
from dotenv import load_dotenv
from fastapi.security import HTTPAuthorizationCredentials


# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Admin credentials (in production, store in database with hashed passwords)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password123")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate hash for a password"""
    return pwd_context.hash(password)

async def authenticate_admin(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate admin user"""
    try:
        # In production, query database for user
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            return {
                "id": 1,
                "username": username,
                "role": "admin",
                "full_name": "System Administrator",
                "email": "admin@company.com",
                "is_active": True,
                "created_at": datetime.now().isoformat()
            }
        return None
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    try:
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

        return encoded_jwt
    except Exception as e:
        logger.error(f"Token creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create access token"
        )

async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")

        if username is None:
            return None

        # In production, query database for user details
        if username == ADMIN_USERNAME and role == "admin":
            return {
                "username": username,
                "role": role,
                "id": 1,
                "full_name": "System Administrator"
            }

        return None
    except JWTError as e:
        logger.error(f"Token verification error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Token verification unexpected error: {str(e)}")
        return None

def hash_admin_password() -> str:
    """Generate hashed version of admin password for secure storage"""
    return get_password_hash(ADMIN_PASSWORD)

async def get_current_admin_user(credentials: HTTPAuthorizationCredentials = None) -> Dict[str, Any]:
    """Get current authenticated admin user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await verify_token(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

class AuthError(Exception):
    """Custom authentication error"""
    pass

def require_admin_role(user: Dict[str, Any]) -> bool:
    """Check if user has admin role"""
    return user.get("role") == "admin"

async def validate_admin_session(token: str) -> bool:
    """Validate admin session and return True if valid"""
    try:
        user = await verify_token(token)
        return user is not None and require_admin_role(user)
    except Exception:
        return False
