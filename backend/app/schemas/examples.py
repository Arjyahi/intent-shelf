import json
from datetime import datetime, timezone

from app.schemas.catalog import Product, User
from app.schemas.common import SessionEventType, SurfaceName
from app.schemas.events import (
    ImpressionEvent,
    LikeEvent,
    SaveEvent,
    SearchEvent,
    Session,
    SessionEvent,
)
from app.schemas.historical import HistoricalInteraction
from app.schemas.retrieval import SessionRecommendationsRequest


def build_example_models() -> dict[str, object]:
    """
    Build a tiny set of example entities so the Phase 2 schema is concrete.

    The examples are intentionally small and readable. They are not meant to be
    fake training data or a simulation system.
    """

    base_timestamp = datetime(2020, 9, 20, 12, 0, tzinfo=timezone.utc)

    session = Session(
        session_id="sess_example_001",
        user_id="user_demo_001",
        session_start=base_timestamp,
        entry_surface=SurfaceName.HOME_FEED,
    )

    return {
        "product": Product(
            product_id="0108775015",
            product_name="Strap top",
            product_type_name="Vest top",
            product_group_name="Garment Upper body",
            colour_group_name="Black",
            department_name="Jersey Basic",
            section_name="Womens Everyday Basics",
            detail_desc="Jersey top with narrow shoulder straps.",
            image_path="data/raw/images/010/0108775015.jpg",
            has_image=True,
            combined_text=(
                "Strap top | Vest top | Garment Upper body | Black | "
                "Jersey Basic | Womens Everyday Basics | "
                "Jersey top with narrow shoulder straps."
            ),
        ),
        "user": User(
            user_id="user_demo_001",
            club_member_status="ACTIVE",
            fashion_news_frequency="NONE",
            age=29,
            postal_code="hashed_postal_code_example",
            profile_source="hm_customer",
        ),
        "historical_interaction": HistoricalInteraction(
            user_id="user_demo_001",
            product_id="0108775015",
            interaction_timestamp=base_timestamp,
            price=0.050831,
            sales_channel_id=2,
            interaction_strength=1.0,
        ),
        "session": session,
        "session_event": SessionEvent(
            event_id="sevt_example_001",
            session_id=session.session_id,
            user_id=session.user_id,
            product_id="0108775015",
            event_type=SessionEventType.DETAIL_OPEN,
            source_surface=SurfaceName.HOME_FEED,
            rank_position=3,
            source_candidate_type="content",
            event_timestamp=base_timestamp,
        ),
        "search_event": SearchEvent(
            event_id="search_example_001",
            session_id=session.session_id,
            user_id=session.user_id,
            query_text="black summer top",
            num_results=24,
            event_timestamp=base_timestamp,
        ),
        "impression_event": ImpressionEvent(
            event_id="impr_example_001",
            session_id=session.session_id,
            user_id=session.user_id,
            product_id="0108775015",
            surface=SurfaceName.HOME_FEED,
            rank_position=3,
            ranking_strategy="phase2_schema_demo",
            primary_source="content",
            explanation_reason="Because you viewed similar black basics",
            event_timestamp=base_timestamp,
        ),
        "like_event": LikeEvent(
            event_id="like_example_001",
            session_id=session.session_id,
            user_id=session.user_id,
            product_id="0108775015",
            event_timestamp=base_timestamp,
        ),
        "save_event": SaveEvent(
            event_id="save_example_001",
            session_id=session.session_id,
            user_id=session.user_id,
            product_id="0108775015",
            event_timestamp=base_timestamp,
        ),
    }


def build_example_payloads() -> dict[str, dict[str, object]]:
    """Return the example entities as plain JSON-friendly dictionaries."""
    models = build_example_models()
    examples = {
        name: model.model_dump(mode="json")
        for name, model in models.items()
    }

    session = models["session"]
    session_event = models["session_event"]
    like_event = models["like_event"]
    save_event = models["save_event"]

    examples["session_recommendation_request"] = SessionRecommendationsRequest(
        session=session,
        session_events=[session_event],
        like_events=[like_event],
        save_events=[save_event],
        k=12,
        max_recent_events=5,
        exclude_recent_products=True,
    ).model_dump(mode="json")

    return examples


def main() -> int:
    print(json.dumps(build_example_payloads(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
