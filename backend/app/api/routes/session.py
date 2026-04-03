from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_persistence_db_service
from app.schemas.retrieval import (
    SessionRecommendationsRequest,
    SessionRecommendationsResponse,
)
from app.services.persistence import PersistenceService
from app.services.session_retrieval import get_session_retrieval_service

router = APIRouter(prefix="/sessions", tags=["recommendations"])


@router.post("/recommendations", response_model=SessionRecommendationsResponse)
def get_session_recommendations(
    request: SessionRecommendationsRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> SessionRecommendationsResponse:
    try:
        prepared_request = persistence_service.prepare_session_request(request)
        service = get_session_retrieval_service()
        return service.get_recommendations(request=prepared_request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
