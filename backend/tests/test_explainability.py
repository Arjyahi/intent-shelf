from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.routes.feed_explained as feed_explained_route
from app.main import app
from app.schemas.common import SessionEventType, SurfaceName
from app.schemas.events import Session, SessionEvent
from app.schemas.retrieval import (
    BlendedSourceSummary,
    CandidateExplanation,
    CandidateExplanationEvidence,
    ExplainedRerankedCandidate,
    FeedExplainRequest,
    FeedExplainResponse,
    FeedRerankResponse,
    RerankedCandidate,
    RerankingConfig,
    RerankingFeatureSummary,
    RerankingScoreBreakdown,
)
from app.services.ranking_strategies import get_ranking_strategy_registry
from app.services.explainability import FeedExplainabilityService


class FakeRerankingService:
    def __init__(self, response: FeedExplainResponse | object) -> None:
        self.response = response

    def rerank_feed(self, request) -> object:
        return self.response


def build_request(**overrides) -> FeedExplainRequest:
    request_data = {
        "user_id": "user_001",
        "query": "black summer top",
        "session": Session(
            session_id="sess_001",
            user_id="user_001",
            session_start=datetime(2020, 9, 20, 12, 0, tzinfo=timezone.utc),
            entry_surface=SurfaceName.HOME_FEED,
        ),
        "session_events": [
            SessionEvent(
                event_id="sevt_001",
                session_id="sess_001",
                user_id="user_001",
                event_timestamp=datetime(2020, 9, 20, 12, 1, tzinfo=timezone.utc),
                event_type=SessionEventType.DETAIL_OPEN,
                source_surface=SurfaceName.PRODUCT_DETAIL,
                product_id="p_seen",
            )
        ],
        "blended_k": 10,
        "reranked_k": 5,
    }
    request_data.update(overrides)
    return FeedExplainRequest(**request_data)


def build_source_summary(
    source: str,
    score_label: str | None = None,
) -> BlendedSourceSummary:
    return BlendedSourceSummary(
        source=source,
        requested=True,
        used=True,
        requested_k=10,
        returned_count=1,
        weight=1.0,
        normalization_strategy="min_max",
        retrieval_method=f"{source}_retrieval",
        score_label=score_label or f"{source}_score",
        message=None,
        skip_reason=None,
    )


def build_candidate(
    product_id: str,
    contributing_sources: list[str],
    weighted_source_scores: dict[str, float],
    normalized_source_scores: dict[str, float] | None = None,
    raw_source_scores: dict[str, float] | None = None,
    ranking_strategy: str = "default",
    ranking_position: int = 1,
    product_name: str = "Demo product",
    product_type_name: str = "Top",
    product_group_name: str = "Upper body",
    diversity_penalty: float = 0.0,
    repeated_product_type_count: int = 0,
    repeated_product_group_count: int = 0,
) -> RerankedCandidate:
    normalized_source_scores = normalized_source_scores or weighted_source_scores
    raw_source_scores = raw_source_scores or normalized_source_scores
    blended_score = sum(weighted_source_scores.values())
    source_count = len(contributing_sources)
    multi_source_signal = max(0.0, min(source_count - 1, 3) / 3.0)

    return RerankedCandidate(
        product_id=product_id,
        product_name=product_name,
        product_type_name=product_type_name,
        product_group_name=product_group_name,
        colour_group_name=None,
        department_name=None,
        image_path=None,
        has_image=False,
        blended_score=blended_score,
        contributing_sources=contributing_sources,
        raw_source_scores=raw_source_scores,
        normalized_source_scores=normalized_source_scores,
        weighted_source_scores=weighted_source_scores,
        source_rank_positions={
            source: index + 1 for index, source in enumerate(contributing_sources)
        },
        source_weights={source: 1.0 for source in contributing_sources},
        ranking_position=ranking_position,
        reranked_score=blended_score - diversity_penalty,
        base_reranking_score=blended_score,
        ranking_strategy=ranking_strategy,
        reranking_features=RerankingFeatureSummary(
            blended_score=blended_score,
            search_signal=normalized_source_scores.get("search", 0.0),
            search_presence=1.0 if "search" in contributing_sources else 0.0,
            session_signal=normalized_source_scores.get("session", 0.0),
            session_presence=1.0 if "session" in contributing_sources else 0.0,
            content_signal=normalized_source_scores.get("content", 0.0),
            collaborative_signal=normalized_source_scores.get("collaborative", 0.0),
            popularity_signal=0.0,
            multi_source_signal=multi_source_signal,
            exact_anchor_penalty=0.0,
            diversity_penalty=diversity_penalty,
            source_count=source_count,
            repeated_product_type_count=repeated_product_type_count,
            repeated_product_group_count=repeated_product_group_count,
        ),
        score_breakdown=RerankingScoreBreakdown(
            blended_component=blended_score,
            search_component=weighted_source_scores.get("search", 0.0),
            search_presence_component=0.0,
            session_component=weighted_source_scores.get("session", 0.0),
            session_presence_component=0.0,
            content_component=weighted_source_scores.get("content", 0.0),
            collaborative_component=weighted_source_scores.get("collaborative", 0.0),
            popularity_component=0.0,
            multi_source_component=0.0,
            exact_anchor_penalty_component=0.0,
            diversity_penalty_component=diversity_penalty,
        ),
    )


def build_response(
    results: list[RerankedCandidate],
    source_summaries: list[BlendedSourceSummary],
) -> FeedRerankResponse:
    used_sources = [summary.source for summary in source_summaries if summary.used]
    strategy_resolution = get_ranking_strategy_registry().resolve_strategy("default")
    return FeedRerankResponse(
        ranking_strategy="default",
        requested_ranking_strategy="default",
        strategy_resolution=strategy_resolution.to_schema(),
        reranked_k=5,
        blended_candidate_count=len(results),
        returned_candidate_count=len(results),
        normalization_strategy="min_max",
        dedup_key="product_id",
        used_sources=used_sources,
        source_weights={source: 1.0 for source in used_sources},
        effective_reranking_config=RerankingConfig(),
        message=None,
        source_summaries=source_summaries,
        results=results,
    )


def test_search_dominant_candidate_gets_search_explanation() -> None:
    candidate = build_candidate(
        product_id="p_search",
        product_name="Black summer top",
        contributing_sources=["search"],
        weighted_source_scores={"search": 1.3},
        normalized_source_scores={"search": 1.0},
        raw_source_scores={"search": 0.91},
    )
    rerank_response = build_response(
        results=[candidate],
        source_summaries=[build_source_summary("search")],
    )
    service = FeedExplainabilityService(
        reranking_service=FakeRerankingService(rerank_response)
    )

    response = service.explain_feed(build_request(query="  black   summer top  "))

    explanation = response.results[0].explanation
    assert explanation.short_reason == 'Because you searched for "black summer top"'
    assert explanation.reason_tags == ["search_match"]
    assert explanation.explanation_source == "search"
    assert explanation.evidence is not None
    assert explanation.evidence.rule_name == "search_dominant"
    assert explanation.evidence.dominant_source == "search"


def test_session_driven_candidate_gets_session_explanation() -> None:
    candidate = build_candidate(
        product_id="p_session",
        product_name="Viewed-again cardigan",
        product_type_name="Cardigan",
        contributing_sources=["session"],
        weighted_source_scores={"session": 1.2},
        normalized_source_scores={"session": 1.0},
        raw_source_scores={"session": 0.88},
    )
    rerank_response = build_response(
        results=[candidate],
        source_summaries=[build_source_summary("session")],
    )
    service = FeedExplainabilityService(
        reranking_service=FakeRerankingService(rerank_response)
    )

    response = service.explain_feed(
        build_request(
            query=None,
            anchor_product_id=None,
        )
    )

    explanation = response.results[0].explanation
    assert explanation.short_reason == "Similar to items you recently viewed"
    assert explanation.reason_tags == ["session_signal", "recent_views"]
    assert explanation.explanation_source == "session"
    assert explanation.evidence is not None
    assert explanation.evidence.rule_name == "session_dominant"
    assert explanation.evidence.session_context_used is True


def test_collaborative_only_candidate_gets_collaborative_explanation() -> None:
    candidate = build_candidate(
        product_id="p_collab",
        product_name="Similar-shopper dress",
        product_type_name="Dress",
        product_group_name="Full body",
        contributing_sources=["collaborative"],
        weighted_source_scores={"collaborative": 1.0},
        normalized_source_scores={"collaborative": 1.0},
        raw_source_scores={"collaborative": 0.77},
    )
    rerank_response = build_response(
        results=[candidate],
        source_summaries=[build_source_summary("collaborative", score_label="implicit_bpr")],
    )
    service = FeedExplainabilityService(
        reranking_service=FakeRerankingService(rerank_response)
    )

    response = service.explain_feed(
        build_request(
            query=None,
            anchor_product_id=None,
            session_events=[],
            like_events=[],
            save_events=[],
        )
    )

    explanation = response.results[0].explanation
    assert explanation.short_reason == "Popular among users with similar purchase history"
    assert explanation.reason_tags == ["collaborative_signal"]
    assert explanation.explanation_source == "collaborative"
    assert explanation.evidence is not None
    assert explanation.evidence.rule_name == "collaborative_dominant"
    assert explanation.evidence.collaborative_is_popularity is False


def test_low_signal_candidate_falls_back_cleanly() -> None:
    candidate = build_candidate(
        product_id="p_fallback",
        product_name="Low-signal top",
        contributing_sources=["search"],
        weighted_source_scores={"search": 0.05},
        normalized_source_scores={"search": 0.04},
        raw_source_scores={"search": 0.04},
    )
    rerank_response = build_response(
        results=[candidate],
        source_summaries=[build_source_summary("search")],
    )
    service = FeedExplainabilityService(
        reranking_service=FakeRerankingService(rerank_response)
    )

    response = service.explain_feed(build_request())

    explanation = response.results[0].explanation
    assert explanation.short_reason == "Recommended using your search signals"
    assert explanation.reason_tags == ["fallback"]
    assert explanation.explanation_source == "fallback"
    assert explanation.evidence is not None
    assert explanation.evidence.rule_name == "fallback"


def test_explain_endpoint_returns_explanation_fields(monkeypatch) -> None:
    class FakeService:
        def explain_feed(self, request: FeedExplainRequest) -> FeedExplainResponse:
            strategy_resolution = get_ranking_strategy_registry().resolve_strategy(
                request.ranking_strategy
            )
            return FeedExplainResponse(
                ranking_strategy=strategy_resolution.definition.key,
                requested_ranking_strategy=request.ranking_strategy,
                strategy_resolution=strategy_resolution.to_schema(),
                reranked_k=request.reranked_k or request.blended_k,
                blended_candidate_count=1,
                returned_candidate_count=1,
                normalization_strategy="min_max",
                dedup_key="product_id",
                used_sources=["search"],
                source_weights={"search": 1.0},
                effective_reranking_config=RerankingConfig(),
                message=None,
                source_summaries=[build_source_summary("search")],
                explanation_mode="deterministic_rule_based",
                explanation_options=request.explanation_options,
                results=[
                    ExplainedRerankedCandidate(
                        **build_candidate(
                            product_id="p1",
                            contributing_sources=["search"],
                            weighted_source_scores={"search": 1.3},
                            normalized_source_scores={"search": 1.0},
                            raw_source_scores={"search": 0.9},
                        ).model_dump(),
                        explanation=CandidateExplanation(
                            short_reason='Because you searched for "black top"',
                            supporting_reasons=[],
                            reason_tags=["search_match"],
                            explanation_source="search",
                            evidence=CandidateExplanationEvidence(
                                rule_name="search_dominant",
                                dominant_source="search",
                                dominant_raw_score=0.9,
                                dominant_normalized_score=1.0,
                                dominant_weighted_score=1.3,
                                contributing_sources=["search"],
                                meaningful_sources=["search"],
                                query_present=True,
                                query_text="black top",
                                normalized_query="black top",
                                session_context_used=False,
                                session_signal_count=0,
                                anchor_product_used=False,
                                anchor_product_id=None,
                                collaborative_is_popularity=False,
                                source_count=1,
                                multi_source_signal=0.0,
                                diversity_penalty=0.0,
                            ),
                        ),
                    )
                ],
            )

    monkeypatch.setattr(
        feed_explained_route,
        "get_feed_explainability_service",
        lambda: FakeService(),
    )

    client = TestClient(app)
    response = client.post(
        "/feed/explain",
        json={
            "query": "black top",
            "blended_k": 10,
            "reranked_k": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["explanation_mode"] == "deterministic_rule_based"
    assert payload["strategy_resolution"]["resolved_key"] == "default"
    assert payload["results"][0]["explanation"]["short_reason"] == (
        'Because you searched for "black top"'
    )
    assert payload["results"][0]["explanation"]["reason_tags"] == ["search_match"]
