from fastapi import APIRouter

from app.api.routes.feed_candidates import router as feed_candidates_router
from app.api.routes.feed_explained import router as feed_explained_router
from app.api.routes.feed_ranked import router as feed_ranked_router
from app.api.routes.health import router as health_router
from app.api.routes.persistence import router as persistence_router
from app.api.routes.products import router as products_router
from app.api.routes.ranking_strategies import router as ranking_strategies_router
from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.session import router as session_router
from app.api.routes.search import router as search_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(persistence_router)
api_router.include_router(products_router)
api_router.include_router(recommendations_router)
api_router.include_router(search_router)
api_router.include_router(session_router)
api_router.include_router(feed_candidates_router)
api_router.include_router(feed_ranked_router)
api_router.include_router(feed_explained_router)
api_router.include_router(ranking_strategies_router)

# TODO(api-versioning): add versioned routers when the feed APIs stabilize.
