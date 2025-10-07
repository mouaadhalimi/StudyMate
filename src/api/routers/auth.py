
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, constr
from sqlalchemy.orm import Session
from datetime import datetime
from ..deps import get_db, create_jwt, hash_password, verify_password, get_current_user
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])

class SignupIn(BaseModel):
    """Input schema for user signup."""
    email: EmailStr
    username: constr(min_length=3, max_length=50)# type: ignore
    password: constr(min_length=8)# type: ignore

class SignupOut(BaseModel):
    """Response schema for successful signup."""
    id: int
    email: EmailStr
    username: str

class LoginIn(BaseModel):
    """Input schema for user login."""
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    """Response schema for login token."""
    access_token: str
    token_type: str = "bearer"

class ChangePasswordIn(BaseModel):
    """Input schema for changing password."""
    old_password: str
    new_password: constr(min_length=8)# type: ignore

@router.post("/signup", response_model=SignupOut, status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db))-> SignupOut:
    """
    Register a new user in the system.

    This endpoint creates a new user account after validating
    that the email and username are not already in use.
    The user's password is securely hashed before storing it.

    Args:
        body (SignupIn): Incoming signup data including email, username, and password.
        db (Session): SQLAlchemy database session dependency.

    Raises:
        HTTPException: 
            - 409 if the email is already registered.
            - 409 if the username is already taken.

    Returns:
        SignupOut: The created user's public information (id, email, username).
    """
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "Email already registered")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(409, "Username taken")
    u = User(email=body.email, username=body.username, password_hash=hash_password(body.password), created_at=datetime.utcnow())
    db.add(u); db.commit(); db.refresh(u)
    return SignupOut(id=u.id, email=u.email, username=u.username)

@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db))-> TokenOut:
    """
    Authenticate a user and return a JWT access token.

    This endpoint verifies the provided email and password.
    If authentication succeeds, it issues a JWT token that can be
    used for authenticated requests.

    Args:
        body (LoginIn): Login credentials (email and password).
        db (Session): SQLAlchemy database session dependency.

    Raises:
        HTTPException: 401 if credentials are invalid.

    Returns:
        TokenOut: Access token and token type (bearer).
    """
    u = db.query(User).filter(User.email == body.email).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = create_jwt(u.id)
    return TokenOut(access_token=token)

@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordIn, 
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user)
    )-> None:
    """
    Change the password for the currently authenticated user.

    The endpoint verifies the user's old password before updating
    it with the new one. The new password is securely hashed before saving.

    Args:
        body (ChangePasswordIn): Old and new password data.
        db (Session): SQLAlchemy database session dependency.
        user (User): Currently authenticated user (injected via dependency).

    Raises:
        HTTPException: 401 if the old password does not match.

    Returns:
        None: Returns HTTP 204 No Content on success.
    """
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    user.password_hash = hash_password(body.new_password)
    db.add(user); db.commit()
    return
