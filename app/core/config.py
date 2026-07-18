import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Upgrader Personal Finance Advisory"
    DEVELOPER_NAME: str = "SURYA V"
    DEBUG: bool = True

    # Database URL: defaults to a local SQLite file so it runs immediately out-of-the-box,
    # but can be easily overridden with a Supabase PostgreSQL URL.
    DATABASE_URL: str = "sqlite+aiosqlite:///./upgrader.db"

    # JWT Authentication settings (for local HTTP-only session cookie)
    JWT_SECRET_KEY: str = "39fca6d8e235cb58d51db09df95b3648a8cfd6f8be225438865615d9cf7bdf41"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Firebase Authentication & Database Configuration
    FIREBASE_API_KEY: Optional[str] = None
    FIREBASE_AUTH_DOMAIN: Optional[str] = None
    FIREBASE_PROJECT_ID: str = "upgrader-finance-mock"
    FIREBASE_STORAGE_BUCKET: Optional[str] = None
    FIREBASE_MESSAGING_SENDER_ID: Optional[str] = None
    FIREBASE_APP_ID: Optional[str] = None
    FIREBASE_MEASUREMENT_ID: Optional[str] = None
    FIREBASE_CREDENTIALS_FILE: Optional[str] = None

    # Enable mock mode fallback for testing if Firebase keys are not provided
    MOCK_FIREBASE: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
