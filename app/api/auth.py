from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import verify_firebase_token, create_access_token, get_current_user
from app.models.user import User, UserResponse

from app.models.activity import ActivityLog

router = APIRouter()

class LoginRequest(BaseModel):
    id_token: str

@router.post("/login", response_model=UserResponse)
async def login_user(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a Firebase ID Token for a secure, HTTP-only local session cookie.
    Upserts the User model instance inside the Supabase database.
    """
    try:
        decoded_token = await verify_firebase_token(payload.id_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication exchange failure: {str(e)}"
        )
    
    uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    name = decoded_token.get("name")
    
    if not uid or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decoded token is missing uid or email identifiers"
        )
    
    # Query for existing user records (Upsert logic)
    query = select(User).where(User.id == uid)
    result = await db.execute(query)
    user = result.scalars().first()
    
    if not user:
        # Create user entry if not registered locally
        user = User(id=uid, email=email, name=name)
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not initialize user records: {str(e)}"
            )
    else:
        # Update user attributes dynamically if changed
        is_modified = False
        if user.name != name:
            user.name = name
            is_modified = True
        if user.email != email:
            user.email = email
            is_modified = True
            
        if is_modified:
            try:
                await db.commit()
                await db.refresh(user)
            except Exception:
                await db.rollback()
                # Suppress error for trivial attribute updates to ensure login flow doesn't block

    # Log USER_LOGIN activity
    try:
        activity = ActivityLog(
            user_id=user.id,
            action_type="USER_LOGIN",
            description=f"Account owner '{user.name or user.email}' signed in."
        )
        db.add(activity)
        await db.commit()
    except Exception:
        await db.rollback()

    # Generate the local secure JWT token
    token_claims = {"sub": user.id, "email": user.email}
    session_jwt = create_access_token(data=token_claims)
    
    # Set the cookie with proper security attributes
    from app.core.config import settings
    response.set_cookie(
        key="session_token",
        value=session_jwt,
        httponly=True,
        secure=not settings.DEBUG,  # False in debug mode to allow localhost HTTP testing
        samesite="lax",
        max_age=3600 * 24  # 24 hour duration
    )
    
    return user

@router.post("/logout")
async def logout_user(
    response: Response,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Clears the HTTP-only session cookie to terminate the user session."""
    if current_user:
        try:
            activity = ActivityLog(
                user_id=current_user.id,
                action_type="USER_LOGOUT",
                description="Account owner signed out of active session."
            )
            db.add(activity)
            await db.commit()
        except Exception:
            await db.rollback()

    from app.core.config import settings
    response.delete_cookie(
        key="session_token",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax"
    )
    return {"message": "Session terminated successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieves current user identity profile using active session context."""
    return current_user

class UserUpdate(BaseModel):
    name: Optional[str] = None

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Updates user profile information and logs activity."""
    old_name = current_user.name
    if payload.name is not None:
        current_user.name = payload.name.strip()
    try:
        activity = ActivityLog(
            user_id=current_user.id,
            action_type="PROFILE_UPDATE",
            description=f"Account display name updated from '{old_name}' to '{current_user.name}'."
        )
        db.add(activity)
        await db.commit()
        await db.refresh(current_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )
    return current_user
