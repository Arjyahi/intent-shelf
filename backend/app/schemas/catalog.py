from typing import Literal

from pydantic import Field

from app.schemas.common import IntentShelfSchema


class Product(IntentShelfSchema):
    """
    Canonical product entity used across offline data and app runtime surfaces.

    This mirrors the cleaned Phase 1 product table closely so later retrieval,
    search, and explanation code can depend on one stable product shape.
    """

    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_type_name: str | None = None
    product_group_name: str | None = None
    graphical_appearance_name: str | None = None
    colour_group_name: str | None = None
    perceived_colour_value_name: str | None = None
    perceived_colour_master_name: str | None = None
    department_name: str | None = None
    index_name: str | None = None
    index_group_name: str | None = None
    section_name: str | None = None
    garment_group_name: str | None = None
    detail_desc: str | None = None
    image_path: str | None = None
    has_image: bool = False
    combined_text: str = ""
    is_active: bool = True


class User(IntentShelfSchema):
    """
    Canonical user entity used by the app layer.

    The current version intentionally stays small. It can represent either a
    seeded H&M customer profile or a later runtime-only app user.
    """

    user_id: str = Field(..., min_length=1)
    club_member_status: str | None = None
    fashion_news_frequency: str | None = None
    age: float | None = Field(default=None, ge=0)
    postal_code: str | None = None
    profile_source: Literal["hm_customer", "intentshelf_runtime"] = "hm_customer"
