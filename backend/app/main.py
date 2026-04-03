from fastapi import FastAPI

from app.api.router import api_router
from app.core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    description=(
        "Backend API for IntentShelf, a fashion discovery system with "
        "multi-source retrieval, blending, transparent reranking, "
        "deterministic explainability, and PostgreSQL-backed runtime "
        "persistence."
    ),
)

app.include_router(api_router)
