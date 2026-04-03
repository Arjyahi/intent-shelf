from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.routes.feed_ranked as feed_ranked_route
from app.main import app
from app.schemas.common import SessionEventType, SurfaceName
from app.schemas.events import Session, SessionEvent
from app.schemas.retrieval import (
    BlendedCandidate,
    BlendedCandidatesResponse,
    BlendedSourceSummary,
    FeedRerankRequest,
    FeedRerankResponse,
    RerankedCandidate,
    RerankingConfig,
    RerankingFeatureSummary,
    RerankingScoreBreakdown,
)
from app.services.ranking_strategies import get_ranking_strategy_registry
from app.services.reranking import FeedRerankingService


class FakeCandidateBlendingService:
    def __init__(self, response: BlendedCandidatesResponse) -> None:
        self.response = response

    def blend_candidates(self, request) -> BlendedCandidatesResponse:
        return self.response


def build_request(**overrides) -> FeedRerankRequest:
    request_data = {
        "query": "black top",
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
    return FeedRerankRequest(**request_data)


def build_candidate(
    product_id: str,
    product_name: str,
    product_type_name: str,
    product_group_name: str,
    blended_score: float,
    contributing_sources: list[str],
    normalized_source_scores: dict[str, float],
) -> BlendedCandidate:
    return BlendedCandidate(
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
        raw_source_scores={source: score for source, score in normalized_source_scores.items()},
        normalized_source_scores=normalized_source_scores,
        weighted_source_scores=normalized_source_scores,
        source_rank_positions={
            source: index + 1 for index, source in enumerate(contributing_sources)
        },
        source_weights={source: 1.0 for source in contributing_sources},
    )


def build_blended_response(results: list[BlendedCandidate]) -> BlendedCandidatesResponse:
    used_sources = sorted(
        {
            source
            for result in results
            for source in result.contributing_sources
        }
    )
    source_summaries = [
        BlendedSourceSummary(
            source=source,
            requested=True,
            used=True,
            requested_k=10,
            returned_count=sum(1 for result in results if source in result.contributing_sources),
            weight=1.0,
            normalization_strategy="min_max",
            retrieval_method=f"{source}_retrieval",
            score_label=f"{source}_score",
            message=None,
            skip_reason=None,
        )
        for source in used_sources
    ]
    return BlendedCandidatesResponse(
        blended_k=10,
        returned_candidate_count=len(results),
        normalization_strategy="min_max",
        dedup_key="product_id",
        used_sources=used_sources,
        source_weights={source: 1.0 for source in used_sources},
        message=None,
        source_summaries=source_summaries,
        results=results,
    )


def test_reranking_order_changes_when_strategy_changes() -> None:
    blended_response = build_blended_response(
        [
            build_candidate(
                product_id="p_search",
                product_name="Black search top",
                product_type_name="Top",
                product_group_name="Upper body",
                blended_score=1.0,
                contributing_sources=["search"],
                normalized_source_scores={"search": 1.0},
            ),
            build_candidate(
                product_id="p_session",
                product_name="Session cardigan",
                product_type_name="Cardigan",
                product_group_name="Upper body",
                blended_score=1.0,
                contributing_sources=["session"],
                normalized_source_scores={"session": 1.0},
            ),
        ]
    )
    service = FeedRerankingService(
        candidate_blending_service=FakeCandidateBlendingService(blended_response)
    )

    default_response = service.rerank_feed(build_request(ranking_strategy="default"))
    search_response = service.rerank_feed(
        build_request(ranking_strategy="search_intent_boosted")
    )

    assert default_response.results[0].product_id == "p_session"
    assert search_response.results[0].product_id == "p_search"
    assert default_response.strategy_resolution.used_fallback is False
    assert search_response.strategy_resolution.resolved_key == "search_intent_boosted"


def test_reranking_diversity_penalty_changes_top_order() -> None:
    blended_response = build_blended_response(
        [
            build_candidate(
                product_id="p1",
                product_name="Black top",
                product_type_name="Top",
                product_group_name="Upper body",
                blended_score=1.1,
                contributing_sources=["search"],
                normalized_source_scores={"search": 1.0},
            ),
            build_candidate(
                product_id="p2",
                product_name="White top",
                product_type_name="Top",
                product_group_name="Upper body",
                blended_score=1.05,
                contributing_sources=["search"],
                normalized_source_scores={"search": 0.9},
            ),
            build_candidate(
                product_id="p3",
                product_name="Blue dress",
                product_type_name="Dress",
                product_group_name="Full body",
                blended_score=0.92,
                contributing_sources=["search"],
                normalized_source_scores={"search": 0.8},
            ),
        ]
    )
    service = FeedRerankingService(
        candidate_blending_service=FakeCandidateBlendingService(blended_response)
    )

    response = service.rerank_feed(build_request())

    assert [candidate.product_id for candidate in response.results[:3]] == ["p1", "p3", "p2"]
    assert response.results[2].reranking_features.diversity_penalty > 0.0
    assert response.results[2].reranking_features.repeated_product_type_count >= 1


def test_reranking_handles_empty_candidate_pool_cleanly() -> None:
    empty_response = BlendedCandidatesResponse(
        blended_k=10,
        returned_candidate_count=0,
        normalization_strategy="min_max",
        dedup_key="product_id",
        used_sources=[],
        source_weights={},
        message="No candidate sources were requested. Provide at least one of user_id, query, anchor_product_id, or session events.",
        source_summaries=[],
        results=[],
    )
    service = FeedRerankingService(
        candidate_blending_service=FakeCandidateBlendingService(empty_response)
    )

    response = service.rerank_feed(build_request(query=None, session_events=[], reranked_k=3))

    assert response.results == []
    assert response.blended_candidate_count == 0
    assert response.message == empty_response.message


def test_unknown_strategy_key_falls_back_to_default() -> None:
    blended_response = build_blended_response(
        [
            build_candidate(
                product_id="p_search",
                product_name="Black search top",
                product_type_name="Top",
                product_group_name="Upper body",
                blended_score=1.0,
                contributing_sources=["search"],
                normalized_source_scores={"search": 1.0},
            )
        ]
    )
    service = FeedRerankingService(
        candidate_blending_service=FakeCandidateBlendingService(blended_response)
    )

    response = service.rerank_feed(build_request(ranking_strategy="unknown_strategy"))

    assert response.requested_ranking_strategy == "unknown_strategy"
    assert response.ranking_strategy == "default"
    assert response.strategy_resolution.used_fallback is True
    assert response.strategy_resolution.resolved_key == "default"
    assert response.strategy_resolution.strategy.name == "Default"


def test_rerank_preblended_candidates_matches_rerank_feed() -> None:
    blended_response = build_blended_response(
        [
            build_candidate(
                product_id="p1",
                product_name="Black top",
                product_type_name="Top",
                product_group_name="Upper body",
                blended_score=1.0,
                contributing_sources=["collaborative", "content"],
                normalized_source_scores={"collaborative": 1.0, "content": 0.8},
            ),
            build_candidate(
                product_id="p2",
                product_name="Blue dress",
                product_type_name="Dress",
                product_group_name="Full body",
                blended_score=0.95,
                contributing_sources=["collaborative"],
                normalized_source_scores={"collaborative": 0.9},
            ),
        ]
    )
    service = FeedRerankingService(
        candidate_blending_service=FakeCandidateBlendingService(blended_response)
    )
    request = build_request(anchor_product_id="p_anchor", ranking_strategy="default")

    feed_response = service.rerank_feed(request)
    preblended_response = service.rerank_preblended_candidates(
        request=request,
        blended_response=blended_response,
    )

    assert [candidate.product_id for candidate in preblended_response.results] == [
        candidate.product_id for candidate in feed_response.results
    ]
    assert preblended_response.effective_reranking_config == feed_response.effective_reranking_config
    assert preblended_response.strategy_resolution == feed_response.strategy_resolution


def test_rerank_endpoint_returns_expected_schema(monkeypatch) -> None:
    class FakeService:
        def rerank_feed(self, request: FeedRerankRequest) -> FeedRerankResponse:
            strategy_resolution = get_ranking_strategy_registry().resolve_strategy(
                request.ranking_strategy
            )
            return FeedRerankResponse(
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
                source_summaries=[],
                results=[
                    RerankedCandidate(
                        product_id="p1",
                        product_name="Black top",
                        product_type_name="Top",
                        product_group_name="Upper body",
                        colour_group_name="Black",
                        department_name="Jersey Basic",
                        image_path=None,
                        has_image=False,
                        blended_score=1.3,
                        contributing_sources=["search"],
                        raw_source_scores={"search": 0.9},
                        normalized_source_scores={"search": 1.0},
                        weighted_source_scores={"search": 1.3},
                        source_rank_positions={"search": 1},
                        source_weights={"search": 1.3},
                        ranking_position=1,
                        reranked_score=1.55,
                        base_reranking_score=1.55,
                        ranking_strategy=request.ranking_strategy,
                        reranking_features=RerankingFeatureSummary(
                            blended_score=1.3,
                            search_signal=1.0,
                            search_presence=1.0,
                            session_signal=0.0,
                            session_presence=0.0,
                            content_signal=0.0,
                            collaborative_signal=0.0,
                            popularity_signal=0.0,
                            multi_source_signal=0.0,
                            exact_anchor_penalty=0.0,
                            diversity_penalty=0.0,
                            source_count=1,
                            repeated_product_type_count=0,
                            repeated_product_group_count=0,
                        ),
                        score_breakdown=RerankingScoreBreakdown(
                            blended_component=1.3,
                            search_component=0.25,
                            search_presence_component=0.0,
                            session_component=0.0,
                            session_presence_component=0.0,
                            content_component=0.0,
                            collaborative_component=0.0,
                            popularity_component=0.0,
                            multi_source_component=0.0,
                            exact_anchor_penalty_component=0.0,
                            diversity_penalty_component=0.0,
                        ),
                    )
                ],
            )

    monkeypatch.setattr(
        feed_ranked_route,
        "get_feed_reranking_service",
        lambda: FakeService(),
    )

    client = TestClient(app)
    response = client.post(
        "/feed/rerank",
        json={
            "query": "black top",
            "ranking_strategy": "search_intent_boosted",
            "blended_k": 10,
            "reranked_k": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_strategy"] == "search_intent_boosted"
    assert payload["requested_ranking_strategy"] == "search_intent_boosted"
    assert payload["strategy_resolution"]["resolved_key"] == "search_intent_boosted"
    assert payload["reranked_k"] == 5
    assert payload["results"][0]["product_id"] == "p1"
