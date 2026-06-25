"""Interview session routes - aggregator."""

from fastapi import APIRouter

from app.api.routes.card_controls import router as card_controls_router
from app.api.routes.session_lifecycle import router as lifecycle_router
from app.api.routes.session_outputs import router as outputs_router
from app.api.routes.utterances import router as utterances_router

router = APIRouter()

# Include all sub-routers (no prefix - paths are already defined in each sub-router)
router.include_router(lifecycle_router)
router.include_router(utterances_router)
router.include_router(card_controls_router)
router.include_router(outputs_router)
