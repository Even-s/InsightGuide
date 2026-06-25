"""Authentication routes.

Currently operates in development mode with placeholder auth.
All endpoints return stub responses — real authentication is not
enforced in the current single-user development setup.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

DEV_USER_ID = "dev-user"


@router.post("/register")
async def register(db: Session = Depends(get_db)):
    """Register a new user. (Development stub)"""
    return {"id": DEV_USER_ID, "message": "Development mode - no registration required"}


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)
):
    """Login and get access token. (Development stub - always succeeds)"""
    access_token = create_access_token(subject=DEV_USER_ID)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
):
    """Get current user information. (Development stub)"""
    return {"id": DEV_USER_ID, "email": "dev@insightguide.local"}
