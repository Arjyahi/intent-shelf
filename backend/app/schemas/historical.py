from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import IntentShelfSchema


class HistoricalInteraction(IntentShelfSchema):
    """
    Offline purchase interaction from the H&M dataset.

    This is deliberately separate from runtime app events. A historical
    purchase tells us what happened in the dataset before the IntentShelf app
    existed; it is not the same thing as an app like, save, impression, or
    within-session click.
    """

    user_id: str = Field(..., min_length=1)
    product_id: str = Field(..., min_length=1)
    interaction_timestamp: datetime
    price: float = Field(..., gt=0)
    sales_channel_id: int | None = None
    interaction_strength: float = Field(default=1.0, ge=0)
    source: Literal["hm_historical"] = "hm_historical"
