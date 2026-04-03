from fastapi import APIRouter, Depends

from app.api.deps import get_persistence_db_service
from app.schemas.retrieval import FeedExplainRequest, FeedExplainResponse
from app.services.persistence import PersistenceService
from app.services.explainability import get_feed_explainability_service

router = APIRouter(prefix="/feed", tags=["feed"])


@router.post("/explain", response_model=FeedExplainResponse)
def explain_feed(
    request: FeedExplainRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> FeedExplainResponse:
    prepared_request = persistence_service.prepare_feed_request(request)
    service = get_feed_explainability_service()
    response = service.explain_feed(request=prepared_request)
    request_id = persistence_service.log_feed_response(
        request_kind="feed_explain",
        request=prepared_request,
        response=response,
    )
    return response.model_copy(update={"request_id": request_id})
