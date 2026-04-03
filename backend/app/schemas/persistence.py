from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import IntentShelfSchema, build_prefixed_id, utc_now
from app.schemas.events import ImpressionEvent, LikeEvent, SaveEvent, SearchEvent, Session, SessionEvent


class ActorContext(IntentShelfSchema):
    """Identity context for anonymous sessions and seeded users."""

    session_id: str | None = None
    user_id: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> "ActorContext":
        if not self.session_id and not self.user_id:
            raise ValueError("Provide at least one of session_id or user_id.")
        return self


class ProductSnapshot(IntentShelfSchema):
    """Small product snapshot stored with runtime state rows and events."""

    product_name: str | None = None
    product_type_name: str | None = None
    product_group_name: str | None = None
    colour_group_name: str | None = None
    department_name: str | None = None
    image_path: str | None = None
    explanation: dict[str, Any] | None = None
    contributing_sources: list[str] = Field(default_factory=list)
    discovery_source: str | None = None
    search_query: str | None = None


class LikeMutationRequest(ActorContext):
    event_id: str = Field(default_factory=lambda: build_prefixed_id("like"))
    event_timestamp: datetime = Field(default_factory=utc_now)
    source: Literal["intentshelf_app"] = "intentshelf_app"
    snapshot: ProductSnapshot | None = None


class SaveMutationRequest(ActorContext):
    event_id: str = Field(default_factory=lambda: build_prefixed_id("save"))
    event_timestamp: datetime = Field(default_factory=utc_now)
    source: Literal["intentshelf_app"] = "intentshelf_app"
    snapshot: ProductSnapshot | None = None


class CartItemUpsertRequest(ActorContext):
    quantity: int = Field(..., ge=1, le=99)
    snapshot: ProductSnapshot | None = None


class CartItemResponse(IntentShelfSchema):
    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_type_name: str | None = None
    product_group_name: str | None = None
    image_path: str | None = None
    quantity: int = Field(..., ge=1)
    updated_at: datetime


class RuntimeStateResponse(IntentShelfSchema):
    session: Session | None = None
    session_events: list[SessionEvent] = Field(default_factory=list)
    like_events: list[LikeEvent] = Field(default_factory=list)
    save_events: list[SaveEvent] = Field(default_factory=list)
    cart_items: list[CartItemResponse] = Field(default_factory=list)


class LikeEventsResponse(IntentShelfSchema):
    items: list[LikeEvent] = Field(default_factory=list)


class SaveEventsResponse(IntentShelfSchema):
    items: list[SaveEvent] = Field(default_factory=list)


class CartItemsResponse(IntentShelfSchema):
    items: list[CartItemResponse] = Field(default_factory=list)


class MutationResult(IntentShelfSchema):
    status: Literal["ok"] = "ok"
    message: str | None = None


class SearchEventLogRequest(SearchEvent):
    """Explicit search logging endpoint payload."""


class ImpressionEventsRequest(IntentShelfSchema):
    impressions: list[ImpressionEvent] = Field(default_factory=list)
