from datetime import datetime

from sqlalchemy.orm import Session as OrmSession

from app.db.models import (
    FeedRequestLogRecord,
    ImpressionEventRecord,
    LikeEventRecord,
    SaveEventRecord,
    SearchEventRecord,
    SessionEventRecord,
)
from app.repositories.persistence import PersistenceRepository
from app.schemas.common import SurfaceName, build_prefixed_id, utc_now
from app.schemas.events import ImpressionEvent, LikeEvent, SaveEvent, SearchEvent, Session, SessionEvent
from app.schemas.persistence import CartItemResponse, ProductSnapshot, RuntimeStateResponse
from app.schemas.retrieval import FeedExplainRequest, FeedExplainResponse, FeedRerankRequest, FeedRerankResponse, SessionRecommendationsRequest
from app.services.product_catalog import ProductCatalogService, get_product_catalog_service

DEFAULT_BOOTSTRAP_SESSION_EVENT_LIMIT = 24


def build_actor_key(user_id: str | None, session_id: str | None) -> str:
    if user_id:
        return f"user:{user_id}"
    if session_id:
        return f"session:{session_id}"
    raise ValueError("Provide at least one of user_id or session_id.")


def merge_snapshot_data(
    product_id: str,
    snapshot: ProductSnapshot | None,
    catalog: ProductCatalogService,
) -> dict[str, object]:
    merged = dict(catalog.get_snapshot(product_id))
    if snapshot is not None:
        merged.update(snapshot.model_dump(exclude_none=True))
    return merged


def build_signal_snapshot(**values: object) -> ProductSnapshot:
    return ProductSnapshot.model_validate(values)


def build_like_event_from_row(row: LikeEventRecord) -> LikeEvent:
    metadata = row.metadata_json or {}
    return LikeEvent(
        event_id=row.event_id,
        session_id=row.session_id,
        user_id=row.user_id,
        event_timestamp=row.event_timestamp,
        source=row.source,
        product_id=row.product_id,
        product_name=metadata.get("product_name"),
        product_type_name=metadata.get("product_type_name"),
        product_group_name=metadata.get("product_group_name"),
        colour_group_name=metadata.get("colour_group_name"),
        department_name=metadata.get("department_name"),
        image_path=metadata.get("image_path"),
        explanation=metadata.get("explanation"),
        contributing_sources=list(metadata.get("contributing_sources", [])),
        discovery_source=metadata.get("discovery_source"),
        search_query=metadata.get("search_query"),
    )


def build_save_event_from_row(row: SaveEventRecord) -> SaveEvent:
    metadata = row.metadata_json or {}
    return SaveEvent(
        event_id=row.event_id,
        session_id=row.session_id,
        user_id=row.user_id,
        event_timestamp=row.event_timestamp,
        source=row.source,
        product_id=row.product_id,
        product_name=metadata.get("product_name"),
        product_type_name=metadata.get("product_type_name"),
        product_group_name=metadata.get("product_group_name"),
        colour_group_name=metadata.get("colour_group_name"),
        department_name=metadata.get("department_name"),
        image_path=metadata.get("image_path"),
        explanation=metadata.get("explanation"),
        contributing_sources=list(metadata.get("contributing_sources", [])),
        discovery_source=metadata.get("discovery_source"),
        search_query=metadata.get("search_query"),
    )


class PersistenceService:
    """Runtime persistence service that stays close to the current app flows."""

    def __init__(
        self,
        db: OrmSession,
        catalog_service: ProductCatalogService | None = None,
    ) -> None:
        self.db = db
        self.repository = PersistenceRepository(db)
        self.catalog_service = catalog_service or get_product_catalog_service()

    def upsert_session(self, session: Session) -> Session:
        record = self.repository.upsert_session(session)
        self.db.commit()
        return Session(
            session_id=record.session_id,
            user_id=record.user_id,
            session_start=record.session_start,
            session_end=record.session_end,
            entry_surface=record.entry_surface,
            source=record.source,
        )

    def ensure_session_context(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        entry_surface: str | None = None,
    ) -> None:
        if not session_id:
            return
        self.repository.upsert_session(
            Session(
                session_id=session_id,
                user_id=user_id,
                session_start=utc_now(),
                entry_surface=entry_surface,
            )
        )

    def persist_session_event(self, event: SessionEvent, commit: bool = True) -> None:
        self.ensure_session_context(
            session_id=event.session_id,
            user_id=event.user_id,
            entry_surface=event.source_surface,
        )
        if not self.repository.event_exists(SessionEventRecord, event.event_id):
            self.repository.add_session_event(
                SessionEventRecord(
                    event_id=event.event_id,
                    session_id=event.session_id,
                    user_id=event.user_id,
                    event_timestamp=event.event_timestamp,
                    event_type=event.event_type,
                    source_surface=event.source_surface,
                    product_id=event.product_id,
                    rank_position=event.rank_position,
                    source_candidate_type=event.source_candidate_type,
                    source=event.source,
                    metadata_json=event.metadata or None,
                )
            )
        if commit:
            self.db.commit()

    def persist_search_event(self, event: SearchEvent, commit: bool = True) -> None:
        self.ensure_session_context(
            session_id=event.session_id,
            user_id=event.user_id,
            entry_surface=SurfaceName.SEARCH_RESULTS.value,
        )
        if not self.repository.event_exists(SearchEventRecord, event.event_id):
            self.repository.add_search_event(
                SearchEventRecord(
                    event_id=event.event_id,
                    session_id=event.session_id,
                    user_id=event.user_id,
                    event_timestamp=event.event_timestamp,
                    query_text=event.query_text,
                    num_results=event.num_results,
                    strategy_used=event.strategy_used,
                    request_id=event.request_id,
                    source=event.source,
                )
            )
        if commit:
            self.db.commit()

    def persist_impression_event(self, event: ImpressionEvent, commit: bool = True) -> None:
        if not self.repository.event_exists(ImpressionEventRecord, event.event_id):
            self.repository.add_impression_event(
                ImpressionEventRecord(
                    event_id=event.event_id,
                    session_id=event.session_id,
                    user_id=event.user_id,
                    event_timestamp=event.event_timestamp,
                    product_id=event.product_id,
                    surface=event.surface,
                    rank_position=event.rank_position,
                    ranking_strategy=event.ranking_strategy,
                    primary_source=event.primary_source,
                    candidate_sources=event.candidate_sources or None,
                    explanation_reason=event.explanation_reason,
                    request_id=event.request_id,
                    source=event.source,
                )
            )
        if commit:
            self.db.commit()

    def persist_like_event(self, event: LikeEvent, commit: bool = True) -> None:
        self.persist_like_state(
            event_id=event.event_id,
            session_id=event.session_id,
            user_id=event.user_id,
            event_timestamp=event.event_timestamp,
            source=event.source,
            product_id=event.product_id,
            is_active=True,
            snapshot=build_signal_snapshot(
                product_name=event.product_name,
                product_type_name=event.product_type_name,
                product_group_name=event.product_group_name,
                colour_group_name=event.colour_group_name,
                department_name=event.department_name,
                image_path=event.image_path,
                explanation=event.explanation,
                contributing_sources=event.contributing_sources,
                discovery_source=event.discovery_source,
                search_query=event.search_query,
            ),
            commit=commit,
        )

    def persist_like_state(
        self,
        *,
        event_id: str,
        session_id: str | None,
        user_id: str | None,
        event_timestamp: datetime,
        source: str,
        product_id: str,
        is_active: bool,
        snapshot: ProductSnapshot | None,
        commit: bool = True,
    ) -> None:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        self.ensure_session_context(
            session_id=session_id,
            user_id=user_id,
            entry_surface=SurfaceName.HOME_FEED.value,
        )
        if not self.repository.event_exists(LikeEventRecord, event_id):
            self.repository.add_like_event(
                LikeEventRecord(
                    event_id=event_id,
                    actor_key=actor_key,
                    session_id=session_id,
                    user_id=user_id,
                    product_id=product_id,
                    event_timestamp=event_timestamp,
                    is_active=is_active,
                    source=source,
                    metadata_json=merge_snapshot_data(product_id, snapshot, self.catalog_service) or None,
                )
            )
        if commit:
            self.db.commit()

    def remove_like(self, *, session_id: str | None, user_id: str | None, product_id: str) -> None:
        self.persist_like_state(
            event_id=build_prefixed_id("like"),
            session_id=session_id,
            user_id=user_id,
            event_timestamp=utc_now(),
            source="intentshelf_app",
            product_id=product_id,
            is_active=False,
            snapshot=None,
            commit=True,
        )

    def persist_save_event(self, event: SaveEvent, commit: bool = True) -> None:
        self.persist_save_state(
            event_id=event.event_id,
            session_id=event.session_id,
            user_id=event.user_id,
            event_timestamp=event.event_timestamp,
            source=event.source,
            product_id=event.product_id,
            is_active=True,
            snapshot=build_signal_snapshot(
                product_name=event.product_name,
                product_type_name=event.product_type_name,
                product_group_name=event.product_group_name,
                colour_group_name=event.colour_group_name,
                department_name=event.department_name,
                image_path=event.image_path,
                explanation=event.explanation,
                contributing_sources=event.contributing_sources,
                discovery_source=event.discovery_source,
                search_query=event.search_query,
            ),
            commit=commit,
        )

    def persist_save_state(
        self,
        *,
        event_id: str,
        session_id: str | None,
        user_id: str | None,
        event_timestamp: datetime,
        source: str,
        product_id: str,
        is_active: bool,
        snapshot: ProductSnapshot | None,
        commit: bool = True,
    ) -> None:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        self.ensure_session_context(
            session_id=session_id,
            user_id=user_id,
            entry_surface=SurfaceName.HOME_FEED.value,
        )
        if not self.repository.event_exists(SaveEventRecord, event_id):
            self.repository.add_save_event(
                SaveEventRecord(
                    event_id=event_id,
                    actor_key=actor_key,
                    session_id=session_id,
                    user_id=user_id,
                    product_id=product_id,
                    event_timestamp=event_timestamp,
                    is_active=is_active,
                    source=source,
                    metadata_json=merge_snapshot_data(product_id, snapshot, self.catalog_service) or None,
                )
            )
        if commit:
            self.db.commit()

    def remove_save(self, *, session_id: str | None, user_id: str | None, product_id: str) -> None:
        self.persist_save_state(
            event_id=build_prefixed_id("save"),
            session_id=session_id,
            user_id=user_id,
            event_timestamp=utc_now(),
            source="intentshelf_app",
            product_id=product_id,
            is_active=False,
            snapshot=None,
            commit=True,
        )

    def upsert_cart_item(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        product_id: str,
        quantity: int,
        snapshot: ProductSnapshot | None,
    ) -> None:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        merged_snapshot = merge_snapshot_data(product_id, snapshot, self.catalog_service)
        product_name = str(merged_snapshot.get("product_name") or "Fashion piece")
        self.ensure_session_context(
            session_id=session_id,
            user_id=user_id,
            entry_surface=SurfaceName.CART.value,
        )
        self.repository.upsert_cart_item(
            actor_key=actor_key,
            session_id=session_id,
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            product_name=product_name,
            product_type_name=merged_snapshot.get("product_type_name"),
            product_group_name=merged_snapshot.get("product_group_name"),
            image_path=merged_snapshot.get("image_path"),
            metadata_json=merged_snapshot or None,
        )
        self.db.commit()

    def remove_cart_item(self, *, session_id: str | None, user_id: str | None, product_id: str) -> None:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        self.repository.remove_cart_item(actor_key, product_id)
        self.db.commit()

    def clear_cart(self, *, session_id: str | None, user_id: str | None) -> None:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        self.repository.clear_cart(actor_key)
        self.db.commit()

    def get_active_like_events(self, *, session_id: str | None, user_id: str | None) -> list[LikeEvent]:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        seen_products: set[str] = set()
        active_events: list[LikeEvent] = []
        for row in self.repository.list_like_events(actor_key):
            if row.product_id in seen_products:
                continue
            seen_products.add(row.product_id)
            if not row.is_active:
                continue
            active_events.append(build_like_event_from_row(row))
        return active_events

    def get_active_save_events(self, *, session_id: str | None, user_id: str | None) -> list[SaveEvent]:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        seen_products: set[str] = set()
        active_events: list[SaveEvent] = []
        for row in self.repository.list_save_events(actor_key):
            if row.product_id in seen_products:
                continue
            seen_products.add(row.product_id)
            if not row.is_active:
                continue
            active_events.append(build_save_event_from_row(row))
        return active_events

    def get_cart_items(self, *, session_id: str | None, user_id: str | None) -> list[CartItemResponse]:
        actor_key = build_actor_key(user_id=user_id, session_id=session_id)
        return [
            CartItemResponse(
                product_id=row.product_id,
                product_name=row.product_name,
                product_type_name=row.product_type_name,
                product_group_name=row.product_group_name,
                image_path=row.image_path,
                quantity=row.quantity,
                updated_at=row.updated_at,
            )
            for row in self.repository.list_cart_items(actor_key)
        ]

    def get_recent_session_events(
        self,
        *,
        session_id: str,
        limit: int = DEFAULT_BOOTSTRAP_SESSION_EVENT_LIMIT,
    ) -> list[SessionEvent]:
        rows = self.repository.list_session_events(session_id, limit)
        return [
            SessionEvent(
                event_id=row.event_id,
                session_id=row.session_id,
                user_id=row.user_id,
                event_timestamp=row.event_timestamp,
                source=row.source,
                event_type=row.event_type,
                source_surface=row.source_surface,
                product_id=row.product_id,
                rank_position=row.rank_position,
                source_candidate_type=row.source_candidate_type,
                metadata=row.metadata_json or {},
            )
            for row in rows
        ]

    def get_runtime_state(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        max_session_events: int = DEFAULT_BOOTSTRAP_SESSION_EVENT_LIMIT,
    ) -> RuntimeStateResponse:
        session = None
        if session_id:
            record = self.repository.get_session(session_id)
            if record is not None:
                session = Session(
                    session_id=record.session_id,
                    user_id=record.user_id,
                    session_start=record.session_start,
                    session_end=record.session_end,
                    entry_surface=record.entry_surface,
                    source=record.source,
                )

        session_events = (
            self.get_recent_session_events(session_id=session_id, limit=max_session_events)
            if session_id
            else []
        )
        like_events = (
            self.get_active_like_events(session_id=session_id, user_id=user_id)
            if (session_id or user_id)
            else []
        )
        save_events = (
            self.get_active_save_events(session_id=session_id, user_id=user_id)
            if (session_id or user_id)
            else []
        )
        cart_items = (
            self.get_cart_items(session_id=session_id, user_id=user_id)
            if (session_id or user_id)
            else []
        )

        return RuntimeStateResponse(
            session=session,
            session_events=session_events,
            like_events=like_events,
            save_events=save_events,
            cart_items=cart_items,
        )

    def prepare_session_request(
        self,
        request: SessionRecommendationsRequest,
    ) -> SessionRecommendationsRequest:
        session_id = request.session.session_id if request.session else None
        user_id = request.session.user_id if request.session else None

        if request.session is not None:
            self.repository.upsert_session(request.session)
        for event in request.session_events:
            self.persist_session_event(event, commit=False)
        for event in request.like_events:
            self.persist_like_event(event, commit=False)
        for event in request.save_events:
            self.persist_save_event(event, commit=False)
        self.db.commit()

        if request.session_events or request.like_events or request.save_events:
            return request

        return request.model_copy(
            update={
                "session_events": (
                    self.get_recent_session_events(
                        session_id=session_id,
                        limit=request.max_recent_events or DEFAULT_BOOTSTRAP_SESSION_EVENT_LIMIT,
                    )
                    if session_id
                    else []
                ),
                "like_events": (
                    self.get_active_like_events(session_id=session_id, user_id=user_id)
                    if (session_id or user_id)
                    else []
                ),
                "save_events": (
                    self.get_active_save_events(session_id=session_id, user_id=user_id)
                    if (session_id or user_id)
                    else []
                ),
            }
        )

    def prepare_feed_request(
        self,
        request: FeedRerankRequest | FeedExplainRequest,
    ) -> FeedRerankRequest | FeedExplainRequest:
        session = request.session
        session_id = session.session_id if session else None
        user_id = request.user_id or (session.user_id if session else None)

        if session is not None:
            self.repository.upsert_session(session)
        for event in request.session_events:
            self.persist_session_event(event, commit=False)
        for event in request.like_events:
            self.persist_like_event(event, commit=False)
        for event in request.save_events:
            self.persist_save_event(event, commit=False)
        self.db.commit()

        if request.session_events or request.like_events or request.save_events:
            return request

        return request.model_copy(
            update={
                "session_events": (
                    self.get_recent_session_events(
                        session_id=session_id,
                        limit=request.max_recent_events or DEFAULT_BOOTSTRAP_SESSION_EVENT_LIMIT,
                    )
                    if session_id
                    else []
                ),
                "like_events": (
                    self.get_active_like_events(session_id=session_id, user_id=user_id)
                    if (session_id or user_id)
                    else []
                ),
                "save_events": (
                    self.get_active_save_events(session_id=session_id, user_id=user_id)
                    if (session_id or user_id)
                    else []
                ),
            }
        )

    def log_feed_response(
        self,
        *,
        request_kind: str,
        request: FeedRerankRequest | FeedExplainRequest,
        response: FeedRerankResponse | FeedExplainResponse,
    ) -> str:
        request_id = build_prefixed_id("freq")
        session_id = request.session.session_id if request.session else None
        user_id = request.user_id or (request.session.user_id if request.session else None)
        created_at = utc_now()

        self.repository.add_feed_request_log(
            FeedRequestLogRecord(
                request_id=request_id,
                request_kind=request_kind,
                session_id=session_id,
                user_id=user_id,
                ranking_strategy=response.ranking_strategy,
                query=request.query,
                anchor_product_id=request.anchor_product_id,
                returned_candidate_count=response.returned_candidate_count,
                blended_candidate_count=response.blended_candidate_count,
                request_metadata={
                    "used_sources": response.used_sources,
                    "source_weights": response.source_weights,
                    "requested_ranking_strategy": request.ranking_strategy,
                    "session_signal_count": len(request.session_events),
                    "like_signal_count": len(request.like_events),
                    "save_signal_count": len(request.save_events),
                },
            )
        )

        for position, candidate in enumerate(response.results, start=1):
            explanation = getattr(candidate, "explanation", None)
            primary_source = candidate.contributing_sources[0] if candidate.contributing_sources else None
            if explanation is not None and getattr(explanation, "explanation_source", None):
                primary_source = explanation.explanation_source

            self.persist_impression_event(
                ImpressionEvent(
                    event_id=f"impr_{request_id}_{position:03d}",
                    session_id=session_id,
                    user_id=user_id,
                    event_timestamp=created_at,
                    product_id=candidate.product_id,
                    surface=(
                        request.session.entry_surface
                        if request.session and request.session.entry_surface
                        else SurfaceName.HOME_FEED.value
                    ),
                    rank_position=getattr(candidate, "ranking_position", position),
                    ranking_strategy=response.ranking_strategy,
                    primary_source=primary_source,
                    candidate_sources=candidate.contributing_sources,
                    explanation_reason=(
                        explanation.short_reason
                        if explanation is not None and getattr(explanation, "short_reason", None)
                        else None
                    ),
                    request_id=request_id,
                ),
                commit=False,
            )

        self.db.commit()
        return request_id


def get_persistence_service(db: OrmSession) -> PersistenceService:
    return PersistenceService(db=db)
