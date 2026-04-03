from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_persistence_db_service
from app.schemas.events import Session, SessionEvent
from app.schemas.persistence import (
    CartItemUpsertRequest,
    CartItemsResponse,
    ImpressionEventsRequest,
    LikeEventsResponse,
    LikeMutationRequest,
    MutationResult,
    RuntimeStateResponse,
    SaveEventsResponse,
    SaveMutationRequest,
    SearchEventLogRequest,
)
from app.services.persistence import PersistenceService

router = APIRouter(tags=["persistence"])


def require_actor(session_id: str | None, user_id: str | None) -> tuple[str | None, str | None]:
    if not session_id and not user_id:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of session_id or user_id.",
        )
    return session_id, user_id


@router.put("/sessions/{session_id}", response_model=Session)
def upsert_session_state(
    session_id: str,
    session: Session,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> Session:
    if session.session_id != session_id:
        raise HTTPException(status_code=400, detail="Path session_id must match body session_id.")
    return persistence_service.upsert_session(session)


@router.post("/sessions/{session_id}/events", response_model=MutationResult)
def log_session_event(
    session_id: str,
    event: SessionEvent,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    if event.session_id != session_id:
        raise HTTPException(status_code=400, detail="Path session_id must match body session_id.")
    persistence_service.persist_session_event(event)
    return MutationResult(message="Session event logged.")


@router.get("/state/bootstrap", response_model=RuntimeStateResponse)
def get_runtime_state(
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    max_session_events: int = Query(default=24, ge=1, le=50),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> RuntimeStateResponse:
    session_id, user_id = require_actor(session_id, user_id)
    return persistence_service.get_runtime_state(
        session_id=session_id,
        user_id=user_id,
        max_session_events=max_session_events,
    )


@router.get("/likes", response_model=LikeEventsResponse)
def get_likes(
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> LikeEventsResponse:
    session_id, user_id = require_actor(session_id, user_id)
    return LikeEventsResponse(
        items=persistence_service.get_active_like_events(session_id=session_id, user_id=user_id)
    )


@router.put("/likes/{product_id}", response_model=MutationResult)
def persist_like(
    product_id: str,
    request: LikeMutationRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    persistence_service.persist_like_state(
        event_id=request.event_id,
        session_id=request.session_id,
        user_id=request.user_id,
        event_timestamp=request.event_timestamp,
        source=request.source,
        product_id=product_id,
        is_active=True,
        snapshot=request.snapshot,
    )
    return MutationResult(message="Like persisted.")


@router.delete("/likes/{product_id}", response_model=MutationResult)
def remove_like(
    product_id: str,
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    session_id, user_id = require_actor(session_id, user_id)
    persistence_service.remove_like(session_id=session_id, user_id=user_id, product_id=product_id)
    return MutationResult(message="Like removed.")


@router.get("/saves", response_model=SaveEventsResponse)
def get_saves(
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> SaveEventsResponse:
    session_id, user_id = require_actor(session_id, user_id)
    return SaveEventsResponse(
        items=persistence_service.get_active_save_events(session_id=session_id, user_id=user_id)
    )


@router.put("/saves/{product_id}", response_model=MutationResult)
def persist_save(
    product_id: str,
    request: SaveMutationRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    persistence_service.persist_save_state(
        event_id=request.event_id,
        session_id=request.session_id,
        user_id=request.user_id,
        event_timestamp=request.event_timestamp,
        source=request.source,
        product_id=product_id,
        is_active=True,
        snapshot=request.snapshot,
    )
    return MutationResult(message="Save persisted.")


@router.delete("/saves/{product_id}", response_model=MutationResult)
def remove_save(
    product_id: str,
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    session_id, user_id = require_actor(session_id, user_id)
    persistence_service.remove_save(session_id=session_id, user_id=user_id, product_id=product_id)
    return MutationResult(message="Save removed.")


@router.get("/cart", response_model=CartItemsResponse)
def get_cart(
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> CartItemsResponse:
    session_id, user_id = require_actor(session_id, user_id)
    return CartItemsResponse(
        items=persistence_service.get_cart_items(session_id=session_id, user_id=user_id)
    )


@router.put("/cart/items/{product_id}", response_model=MutationResult)
def upsert_cart_item(
    product_id: str,
    request: CartItemUpsertRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    persistence_service.upsert_cart_item(
        session_id=request.session_id,
        user_id=request.user_id,
        product_id=product_id,
        quantity=request.quantity,
        snapshot=request.snapshot,
    )
    return MutationResult(message="Cart updated.")


@router.delete("/cart/items/{product_id}", response_model=MutationResult)
def remove_cart_item(
    product_id: str,
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    session_id, user_id = require_actor(session_id, user_id)
    persistence_service.remove_cart_item(
        session_id=session_id,
        user_id=user_id,
        product_id=product_id,
    )
    return MutationResult(message="Cart item removed.")


@router.delete("/cart", response_model=MutationResult)
def clear_cart(
    session_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    session_id, user_id = require_actor(session_id, user_id)
    persistence_service.clear_cart(session_id=session_id, user_id=user_id)
    return MutationResult(message="Cart cleared.")


@router.post("/events/search", response_model=MutationResult)
def log_search_event(
    request: SearchEventLogRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    persistence_service.persist_search_event(request)
    return MutationResult(message="Search event logged.")


@router.post("/events/impressions", response_model=MutationResult)
def log_impressions(
    request: ImpressionEventsRequest,
    persistence_service: PersistenceService = Depends(get_persistence_db_service),
) -> MutationResult:
    for impression in request.impressions:
        persistence_service.persist_impression_event(impression, commit=False)
    persistence_service.db.commit()
    return MutationResult(message="Impressions logged.")
