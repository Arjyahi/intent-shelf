from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_persistence_db_service
from app.schemas.events import SearchEvent
from app.schemas.retrieval import SearchResultsResponse
from app.schemas.common import utc_now
from app.services.search_retrieval import get_search_retrieval_service
from app.services.persistence import PersistenceService

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResultsResponse)
def search_products(
    query: str = Query(..., description="Lexical product search query."),
    k: int = Query(default=20, ge=1, le=100),
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    strategy_used: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> SearchResultsResponse:
    try:
        service = get_search_retrieval_service()
        response = service.search(query=query, k=k)
        if session_id:
            persistence_service.persist_search_event(
                SearchEvent(
                    session_id=session_id,
                    user_id=user_id,
                    event_timestamp=utc_now(),
                    query_text=query,
                    num_results=len(response.results),
                    strategy_used=strategy_used,
                )
            )
        return response
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
