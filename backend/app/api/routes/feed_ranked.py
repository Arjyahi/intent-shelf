from fastapi import APIRouter, Depends

from app.api.deps import get_persistence_db_service
from app.schemas.retrieval import FeedRerankRequest, FeedRerankResponse
from app.services.persistence import PersistenceService
from app.services.reranking import get_feed_reranking_service

router = APIRouter(prefix="/feed", tags=["feed"])


@router.post("/rerank", response_model=FeedRerankResponse)
def rerank_feed(
    request: FeedRerankRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> FeedRerankResponse:
    prepared_request = persistence_service.prepare_feed_request(request)
    service = get_feed_reranking_service()
    response = service.rerank_feed(request=prepared_request)
    request_id = persistence_service.log_feed_response(
        request_kind="feed_rerank",
        request=prepared_request,
        response=response,
    )
    return response.model_copy(update={"request_id": request_id})
