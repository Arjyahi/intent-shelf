from fastapi import APIRouter, HTTPException, Query

from app.schemas.retrieval import CollaborativeRecommendationsResponse
from app.services.collaborative_retrieval import get_collaborative_retrieval_service

router = APIRouter(prefix="/users", tags=["recommendations"])


@router.get(
    "/{user_id}/recommendations/collaborative",
    response_model=CollaborativeRecommendationsResponse,
)
def get_collaborative_recommendations(
    user_id: str,
    k: int = Query(default=20, ge=1, le=100),
    exclude_seen_items: bool = Query(default=True),
) -> CollaborativeRecommendationsResponse:
    try:
        service = get_collaborative_retrieval_service()
        return service.get_recommendations(
            user_id=user_id,
            k=k,
            exclude_seen_items=exclude_seen_items,
        )
    except (FileNotFoundError, ImportError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
