from app.schemas.examples import build_example_models, build_example_payloads


def test_example_models_are_valid_and_timezone_aware() -> None:
    examples = build_example_models()

    assert examples["historical_interaction"].source == "hm_historical"
    assert examples["like_event"].source == "intentshelf_app"
    assert examples["session"].session_start.tzinfo is not None
    assert examples["historical_interaction"].interaction_timestamp.tzinfo is not None
    assert examples["impression_event"].ranking_strategy == "phase2_schema_demo"


def test_example_payloads_are_json_ready() -> None:
    payloads = build_example_payloads()

    assert payloads["product"]["product_id"] == "0108775015"
    assert isinstance(payloads["search_event"]["event_timestamp"], str)
    assert payloads["session_event"]["source_surface"] == "home_feed"
    assert payloads["session_recommendation_request"]["exclude_recent_products"] is True
