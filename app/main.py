from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.models.user import User
from app.models.finance import FinancialLog
from app.models.activity import ActivityLog
from app.api.auth import router as auth_router
from app.api.finance import router as finance_router

def _run_migrations(sync_conn):
    from sqlalchemy import inspect, text
    inspector = inspect(sync_conn)
    if inspector.has_table("activity_logs"):
        columns = [c["name"] for c in inspector.get_columns("activity_logs")]
        if "amount_invested" not in columns:
            sync_conn.execute(text("ALTER TABLE activity_logs ADD COLUMN amount_invested NUMERIC(12, 2)"))

# Lifespan events management (Database table initialization)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dynamically create schemas and tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_run_migrations)
    yield
    # Shutdown steps can be added here if needed


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Upgrader: A mathematically rigorous, responsive, and secure personal finance advisory platform.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Register prefix routes
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(finance_router, prefix="/api/finance", tags=["Finance"])

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Railway, Render, and external monitoring."""
    return {"status": "ok", "app": settings.PROJECT_NAME}

# Setup template renderer
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/")
async def serve_dashboard(request: Request):
    """Serves the premium single-page dashboard page."""
    return templates.TemplateResponse(

        "dashboard.html", 
        {
            "request": request, 
            "project_name": settings.PROJECT_NAME,
            "developer_name": settings.DEVELOPER_NAME,
            "firebase_api_key": settings.FIREBASE_API_KEY,
            "firebase_auth_domain": settings.FIREBASE_AUTH_DOMAIN,
            "firebase_project_id": settings.FIREBASE_PROJECT_ID,
            "firebase_storage_bucket": settings.FIREBASE_STORAGE_BUCKET,
            "firebase_messaging_sender_id": settings.FIREBASE_MESSAGING_SENDER_ID,
            "firebase_app_id": settings.FIREBASE_APP_ID,
            "firebase_measurement_id": settings.FIREBASE_MEASUREMENT_ID
        }
    )
