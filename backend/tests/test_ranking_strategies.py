from fastapi.testclient import TestClient

from app.main import app
from app.services.ranking_strategies import get_ranking_strategy_registry


def test_strategy_registry_lists_expected_strategies() -> None:
    registry = get_ranking_strategy_registry()

    strategies = registry.list_strategies()

    assert [strategy.key for strategy in strategies] == [
        "default",
        "search_intent_boosted",
        "session_boosted",
        "diversity_boosted",
    ]
    assert strategies[0].name == "Default"


def test_strategy_registry_falls_back_for_unknown_key() -> None:
    registry = get_ranking_strategy_registry()

    resolution = registry.resolve_strategy("unknown_strategy")

    assert resolution.requested_key == "unknown_strategy"
    assert resolution.definition.key == "default"
    assert resolution.used_fallback is True


def test_strategy_listing_endpoint_returns_expected_schema() -> None:
    client = TestClient(app)

    response = client.get("/ranking/strategies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_strategy_key"] == "default"
    assert [strategy["key"] for strategy in payload["strategies"]] == [
        "default",
        "search_intent_boosted",
        "session_boosted",
        "diversity_boosted",
    ]
    assert payload["strategies"][1]["description"].startswith(
        "Raises search-related weights"
    )
