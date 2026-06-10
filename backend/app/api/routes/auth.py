"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated

from app.db.session import get_db
from app.core.security import create_access_token, verify_password

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/register")
async def register(db: Session = Depends(get_db)):
    """Register a new user."""
    # TODO: Implement user registration
    return {"message": "User registration endpoint - to be implemented"}


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """Login and get access token."""
    # TODO: Implement user authentication
    # For now, return a placeholder token
    access_token = create_access_token(subject="placeholder-user-id")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    """Get current user information."""
    # TODO: Implement user info retrieval
    return {"message": "Current user endpoint - to be implemented"}
