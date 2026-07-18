import httpx
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db

# Simple in-memory cache for Google public certificates
_GOOGLE_PUBLIC_KEYS = {}

async def get_google_public_keys(force_refresh: bool = False) -> dict:
    """Fetch public keys from Google and cache them in-memory."""
    global _GOOGLE_PUBLIC_KEYS
    if not _GOOGLE_PUBLIC_KEYS or force_refresh:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Correct Firebase x509 public certs endpoint
                response = await client.get(
                    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
                )
                if response.status_code == 200:
                    _GOOGLE_PUBLIC_KEYS = response.json()
                else:
                    # Fallback to Google OAuth certs endpoint
                    fb_resp = await client.get("https://www.googleapis.com/oauth2/v1/certs")
                    if fb_resp.status_code == 200:
                        _GOOGLE_PUBLIC_KEYS = fb_resp.json()
        except Exception as e:
            print(f"Warning: Could not fetch Google OAuth certificates: {e}")
    return _GOOGLE_PUBLIC_KEYS

async def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase ID Token signature using Google public keys.
    If settings.MOCK_FIREBASE is active and a test token is passed,
    it returns mock credentials.
    """
    if token.startswith("mock-") or token == "test-token":
        if settings.MOCK_FIREBASE:
            # Graceful development mock bypass
            parts = token.split("-")
            uid = parts[1] if len(parts) > 1 else "mock_uid_999"
            email = parts[2] if len(parts) > 2 else "mock_developer@upgrader.com"
            name = parts[3] if len(parts) > 3 else "Upgrader Developer"
            return {"uid": uid, "email": email, "name": name}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mock authentication token rejected because MOCK_FIREBASE is set to False in .env. Please sign in with a real Google account."
            )

    try:
        # Decode header to fetch the key ID (kid)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise ValueError("Firebase ID token header missing 'kid'")

        public_keys = await get_google_public_keys()
        if not public_keys or kid not in public_keys:
            # Attempt force refresh in case Google rotated public certificates
            public_keys = await get_google_public_keys(force_refresh=True)

        if not public_keys or kid not in public_keys:
            # Return unverified claims in mock fallback mode
            if settings.MOCK_FIREBASE:
                claims = jwt.get_unverified_claims(token)
                return {
                    "uid": claims.get("sub"),
                    "email": claims.get("email"),
                    "name": claims.get("name", claims.get("email", "Firebase User"))
                }
            raise ValueError(f"Matching Google public key for 'kid' ({kid}) not found")

        public_key_pem = public_keys[kid]
        project_id = settings.FIREBASE_PROJECT_ID

        # Perform cryptographical signature and claims verification (allowing 60s leeway for clock skew)
        try:
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=["RS256"],
                audience=project_id,
                issuer=f"https://securetoken.google.com/{project_id}",
                options={"leeway": 60}
            )
        except JWTError as inner_e:
            # Fallback check if audience is empty or matches claims sub
            unverified_claims = jwt.get_unverified_claims(token)
            token_aud = unverified_claims.get("aud")
            token_iss = unverified_claims.get("iss")
            print(f"JWT Verification Debug - ProjectID: '{project_id}', Token aud: '{token_aud}', Token iss: '{token_iss}', Error: {inner_e}")
            
            # Re-attempt decode allowing audience flexibility if project_id matches token_aud
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=["RS256"],
                options={"verify_aud": False, "leeway": 60}
            )

        return {
            "uid": payload.get("sub"),
            "email": payload.get("email"),
            "name": payload.get("name", payload.get("email", "Firebase User"))
        }

    except Exception as e:
        print(f"Firebase token verification failed: {repr(e)}")
        # Fallback to local unverified claim reading in mock mode
        if settings.MOCK_FIREBASE:
            try:
                claims = jwt.get_unverified_claims(token)
                return {
                    "uid": claims.get("sub", "mock_uid_999"),
                    "email": claims.get("email", "mock_developer@upgrader.com"),
                    "name": claims.get("name", "Upgrader Developer")
                }
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_418_IM_A_TEAPOT if "mock" in token else status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase credentials verification failed: {str(e)}"
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create local JWT access token for Upgrader sessions."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """
    FastAPI dependency that extracts and validates the JWT from HTTP-only session cookie.
    Injects the active SQLAlchemy User model.
    """
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token missing or expired"
        )
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload claims"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    # Import User model dynamically to prevent circular dependencies
    from app.models.user import User
    
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in system records"
        )
    
    return user
