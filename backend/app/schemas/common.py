from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def build_prefixed_id(prefix: str) -> str:
    """Generate a readable identifier for runtime-only entities and events."""
    return f"{prefix}_{uuid4().hex}"


class IntentShelfSchema(BaseModel):
    """Shared defaults for small, explicit backend contracts."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=True,
    )


class SurfaceName(str, Enum):
    HOME_FEED = "home_feed"
    SEARCH_RESULTS = "search_results"
    PRODUCT_DETAIL = "product_detail"
    SIMILAR_ITEMS = "similar_items"
    SAVED_ITEMS = "saved_items"
    SAVED_LIBRARY = "saved_library"
    LIKED_LIBRARY = "liked_library"
    CART = "cart"


class SessionEventType(str, Enum):
    PRODUCT_VIEW = "product_view"
    CLICK = "click"
    DETAIL_OPEN = "detail_open"
    SIMILAR_ITEM_CLICK = "similar_item_click"
