from datetime import datetime, timezone

from sqlalchemy import select

import app.api.routes.feed_explained as feed_explained_route
from app.db.models import FeedRequestLogRecord, ImpressionEventRecord
from app.schemas.events import Session
from app.schemas.retrieval import (
    BlendedSourceSummary,
    CandidateExplanation,
    ExplainedRerankedCandidate,
    FeedExplainResponse,
    RerankingConfig,
    RerankingDiversityConfig,
    RerankingFeatureSummary,
    RerankingFeatureWeights,
    RerankingScoreBreakdown,
)


def build_session_payload() -> dict:
    return {
        "session_id": "sess_test_runtime",
        "user_id": "user_test_runtime",
        "session_start": "2020-09-20T12:00:00Z",
        "entry_surface": "home_feed",
        "source": "intentshelf_app",
    }


def test_save_roundtrip_and_bootstrap_state(client) -> None:
    session = build_session_payload()
    response = client.put(f"/sessions/{session['session_id']}", json=session)
    assert response.status_code == 200

    save_response = client.put(
        "/saves/0108775015",
        json={
            "session_id": session["session_id"],
            "user_id": session["user_id"],
            "event_id": "save_test_001",
            "event_timestamp": "2020-09-20T12:05:00Z",
            "snapshot": {
                "product_name": "Black strap top",
                "product_type_name": "Vest top",
                "product_group_name": "Upper body",
                "image_path": "data/raw/images/010/0108775015.jpg",
                "discovery_source": "feed",
            },
        },
    )
    assert save_response.status_code == 200

    saved_items = client.get(
        f"/saves?session_id={session['session_id']}&user_id={session['user_id']}"
    )
    assert saved_items.status_code == 200
    assert saved_items.json()["items"][0]["product_id"] == "0108775015"

    bootstrap = client.get(
        f"/state/bootstrap?session_id={session['session_id']}&user_id={session['user_id']}"
    )
    assert bootstrap.status_code == 200
    payload = bootstrap.json()
    assert payload["session"]["session_id"] == session["session_id"]
    assert payload["save_events"][0]["product_name"] == "Black strap top"


def test_cart_roundtrip(client) -> None:
    response = client.put(
        "/cart/items/0108775015",
        json={
            "session_id": "sess_cart_001",
            "user_id": "user_cart_001",
            "quantity": 2,
            "snapshot": {
                "product_name": "Black strap top",
                "product_type_name": "Vest top",
                "product_group_name": "Upper body",
                "image_path": "data/raw/images/010/0108775015.jpg",
            },
        },
    )
    assert response.status_code == 200

    cart_response = client.get("/cart?session_id=sess_cart_001&user_id=user_cart_001")
    assert cart_response.status_code == 200
    assert cart_response.json()["items"][0]["quantity"] == 2

    delete_response = client.delete(
        "/cart/items/0108775015?session_id=sess_cart_001&user_id=user_cart_001"
    )
    assert delete_response.status_code == 200

    cart_response = client.get("/cart?session_id=sess_cart_001&user_id=user_cart_001")
    assert cart_response.json()["items"] == []


def test_session_event_roundtrip(client) -> None:
    session = build_session_payload()
    client.put(f"/sessions/{session['session_id']}", json=session)

    response = client.post(
        f"/sessions/{session['session_id']}/events",
        json={
            "event_id": "sevt_runtime_001",
            "session_id": session["session_id"],
            "user_id": session["user_id"],
            "event_timestamp": "2020-09-20T12:03:00Z",
            "event_type": "detail_open",
            "source_surface": "home_feed",
            "product_id": "0108775015",
            "rank_position": 3,
            "source_candidate_type": "search",
            "metadata": {"request_kind": "product_open"},
            "source": "intentshelf_app",
        },
    )
    assert response.status_code == 200

    bootstrap = client.get(
        f"/state/bootstrap?session_id={session['session_id']}&user_id={session['user_id']}"
    )
    assert bootstrap.status_code == 200
    assert bootstrap.json()["session_events"][0]["event_id"] == "sevt_runtime_001"


def test_feed_explain_logs_request_and_impression(client, db_session, monkeypatch) -> None:
    class FakeExplainService:
        def explain_feed(self, request):
            return FeedExplainResponse(
                request_id=None,
                ranking_strategy="default",
                requested_ranking_strategy=request.ranking_strategy,
                strategy_resolution={
                    "requested_key": request.ranking_strategy,
                    "resolved_key": "default",
                    "used_fallback": False,
                    "strategy": {
                        "key": "default",
                        "name": "Default",
                        "description": "Balanced mix",
                    },
                },
                reranked_k=1,
                blended_candidate_count=1,
                returned_candidate_count=1,
                normalization_strategy="min_max",
                dedup_key="product_id",
                used_sources=["search", "session"],
                source_weights={"search": 1.3, "session": 1.2},
                effective_reranking_config=RerankingConfig(
                    feature_weights=RerankingFeatureWeights(),
                    diversity=RerankingDiversityConfig(),
                ),
                message=None,
                source_summaries=[
                    BlendedSourceSummary(
                        source="search",
                        requested=True,
                        used=True,
                        requested_k=20,
                        returned_count=1,
                        weight=1.3,
                        normalization_strategy="min_max",
                        retrieval_method="tfidf",
                        score_label="cosine",
                        message=None,
                        skip_reason=None,
                    )
                ],
                explanation_mode="deterministic_rule_based",
                explanation_options={
                    "include_evidence": True,
                    "max_supporting_reasons": 2,
                },
                results=[
                    ExplainedRerankedCandidate(
                        product_id="0108775015",
                        product_name="Black strap top",
                        product_type_name="Vest top",
                        product_group_name="Upper body",
                        colour_group_name="Black",
                        department_name="Jersey Basic",
                        image_path="data/raw/images/010/0108775015.jpg",
                        has_image=True,
                        blended_score=1.8,
                        contributing_sources=["search", "session"],
                        raw_source_scores={"search": 0.8, "session": 0.6},
                        normalized_source_scores={"search": 1.0, "session": 0.7},
                        weighted_source_scores={"search": 1.3, "session": 0.84},
                        source_rank_positions={"search": 1, "session": 2},
                        source_weights={"search": 1.3, "session": 1.2},
                        ranking_position=1,
                        reranked_score=2.14,
                        base_reranking_score=2.14,
                        ranking_strategy="default",
                        reranking_features=RerankingFeatureSummary(
                            blended_score=1.8,
                            search_signal=1.0,
                            search_presence=1.0,
                            session_signal=0.7,
                            session_presence=1.0,
                            content_signal=0.0,
                            collaborative_signal=0.0,
                            popularity_signal=0.0,
                            multi_source_signal=0.33,
                            exact_anchor_penalty=0.0,
                            diversity_penalty=0.0,
                            source_count=2,
                            repeated_product_type_count=0,
                            repeated_product_group_count=0,
                        ),
                        score_breakdown=RerankingScoreBreakdown(
                            blended_component=1.8,
                            search_component=0.45,
                            search_presence_component=0.15,
                            session_component=0.35,
                            session_presence_component=0.15,
                            content_component=0.0,
                            collaborative_component=0.0,
                            popularity_component=0.0,
                            multi_source_component=0.24,
                            exact_anchor_penalty_component=0.0,
                            diversity_penalty_component=0.0,
                        ),
                        explanation=CandidateExplanation(
                            short_reason='Because you searched for "black top"',
                            supporting_reasons=[],
                            reason_tags=["search_match"],
                            explanation_source="search",
                            evidence=None,
                        ),
                    )
                ],
            )

    monkeypatch.setattr(
        feed_explained_route,
        "get_feed_explainability_service",
        lambda: FakeExplainService(),
    )

    response = client.post(
        "/feed/explain",
        json={
            "user_id": "user_test_runtime",
            "ranking_strategy": "default",
            "query": "black top",
            "session": build_session_payload(),
            "session_events": [],
            "like_events": [],
            "save_events": [],
            "blended_k": 10,
            "reranked_k": 1,
            "explanation_options": {
                "include_evidence": True,
                "max_supporting_reasons": 2,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"]

    feed_log = db_session.scalar(select(FeedRequestLogRecord))
    impression = db_session.scalar(select(ImpressionEventRecord))

    assert feed_log is not None
    assert feed_log.request_kind == "feed_explain"
    assert impression is not None
    assert impression.product_id == "0108775015"
