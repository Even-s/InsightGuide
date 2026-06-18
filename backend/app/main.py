"""FastAPI application entry point for InsightGuide."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import json

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.json_encoder import DateTimeEncoder

# InsightGuide routes
from app.api.routes import documents, sections, question_cards, interview_sessions, auth, realtime, prep_sessions, events, session_reports, brd, prompts, diarize, projects, insight_memos, evidence_matrix

# Setup logging
setup_logging()

# Configure Pydantic to serialize datetime with 'Z' suffix
from pydantic import ConfigDict
from pydantic.json import pydantic_encoder

def custom_encoder(obj):
    """Custom JSON encoder for datetime objects."""
    from datetime import datetime
    if isinstance(obj, datetime):
        # Serialize UTC datetime with 'Z' suffix
        return obj.isoformat() + 'Z'
    return pydantic_encoder(obj)

# Create FastAPI application
app = FastAPI(
    title="InsightGuide API",
    description="AI Requirements Interview Assistant - Backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include InsightGuide routers
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(sections.router, prefix="/api/sections", tags=["sections"])
app.include_router(question_cards.router, prefix="/api/question-cards", tags=["question-cards"])
app.include_router(
    interview_sessions.router,
    prefix="/api/interview-sessions",
    tags=["interview-sessions"],
)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(realtime.router, prefix="/api/realtime", tags=["realtime"])
app.include_router(
    prep_sessions.router,
    prefix="/api/prep-sessions",
    tags=["prep-sessions"],
)
app.include_router(
    session_reports.router,
    prefix="/api/interview-sessions",
    tags=["session-reports"],
)
app.include_router(
    brd.router,
    prefix="/api/brd",
    tags=["brd"],
)
app.include_router(prompts.router, prefix="/api", tags=["prompts"])
app.include_router(diarize.router, prefix="/api/realtime", tags=["diarize"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(insight_memos.router, prefix="/api", tags=["insight-memos"])
app.include_router(evidence_matrix.router, prefix="/api", tags=["evidence-matrix"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "InsightGuide API", "version": "0.1.0", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
        }
    )


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("InsightGuide API starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Seed prompt templates if table is empty
    try:
        from app.db.session import SessionLocal
        from app.models.prompt_template import PromptTemplate
        db = SessionLocal()
        count = db.query(PromptTemplate).count()
        if count == 0:
            from app.services.prompt_seed_data import PROMPT_SEEDS as PROMPTS
            from app.services.prompt_registry_service import prompt_registry_service
            for p in PROMPTS:
                prompt_registry_service.seed_template(
                    db, key=p["key"], name=p["name"], category=p["category"],
                    system_prompt=p["system_prompt"],
                    user_prompt_template=p.get("user_prompt_template"),
                    description=p.get("description"), model=p.get("model"),
                    risk_level=p.get("risk_level", "medium"),
                    service_file=p.get("service_file"),
                    service_function=p.get("service_function"),
                    input_variables=p.get("input_variables"),
                    output_format=p.get("output_format"),
                )
            logger.info(f"Seeded {len(PROMPTS)} prompt templates")
        db.close()
    except Exception as e:
        logger.warning(f"Prompt seed skipped: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("InsightGuide API shutting down...")
