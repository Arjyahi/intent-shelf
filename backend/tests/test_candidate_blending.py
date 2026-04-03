from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.api.routes.feed_candidates as feed_candidates_route
from app.main import app
from app.schemas.common import SessionEventType, SurfaceName
from app.schemas.events import Session, SessionEvent
from app.schemas.retrieval import (
    BlendedCandidate,
    BlendedCandidatesRequest,
    BlendedCandidatesResponse,
    CollaborativeRecommendation,
    CollaborativeRecommendationsResponse,
    SearchResult,
    SearchResultsResponse,
    SessionRecommendation,
    SessionRecommendationsResponse,
    SimilarProduct,
    SimilarProductsResponse,
)
from app.services.candidate_blending import CandidateBlendingService


class FakeCollaborativeService:
    def __init__(self, response: CollaborativeRecommendationsResponse) -> None:
        self.response = response

    def get_recommendations(
        self,
        user_id: str,
        k: int = 20,
        exclude_seen_items: bool = True,
    ) -> CollaborativeRecommendationsResponse:
        return self.response


class FakeContentService:
    def __init__(self, response: SimilarProductsResponse) -> None:
        self.response = response

    def get_similar_products(
        self,
        product_id: str,
        k: int = 12,
    ) -> SimilarProductsResponse:
        return self.response


class FakeSearchService:
    def __init__(self, response: SearchResultsResponse) -> None:
        self.response = response

    def search(self, query: str, k: int = 20) -> SearchResultsResponse:
        return self.response


class FakeSessionService:
    def __init__(self, response: SessionRecommendationsResponse) -> None:
        self.response = response

    def get_recommendations(
        self,
        request,
    ) -> SessionRecommendationsResponse:
        return self.response


def build_request(**overrides) -> BlendedCandidatesRequest:
    request_data = {
        "user_id": "user_001",
        "query": "black top",
        "anchor_product_id": "anchor_001",
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
        "like_events": [],
        "save_events": [],
        "collaborative_k": 2,
        "content_k": 2,
        "search_k": 2,
        "session_k": 2,
        "blended_k": 10,
    }
    request_data.update(overrides)
    return BlendedCandidatesRequest(**request_data)


def build_service() -> CandidateBlendingService:
    collaborative_response = CollaborativeRecommendationsResponse(
        query_user_id="user_001",
        k=2,
        model_name="implicit",
        model_loss="bpr",
        exclude_seen_items=True,
        is_known_user=True,
        score_source="implicit_recommendation",
        fallback_strategy=None,
        message=None,
        results=[
            CollaborativeRecommendation(
                product_id="p1",
                product_name="Black tee",
                product_type_name="T-shirt",
                product_group_name="Upper body",
                image_path=None,
                has_image=False,
                score=0.9,
            ),
            CollaborativeRecommendation(
                product_id="p2",
                product_name="Black tank",
                product_type_name="Vest top",
                product_group_name="Upper body",
                image_path=None,
                has_image=False,
                score=0.6,
            ),
        ],
    )
    content_response = SimilarProductsResponse(
        query_product_id="anchor_001",
        k=2,
        model_name="openai/clip-vit-base-patch32",
        fusion_alpha=0.6,
        results=[
            SimilarProduct(
                product_id="p1",
                product_name="Black tee",
                product_type_name="T-shirt",
                product_group_name="Upper body",
                image_path=None,
                has_image=False,
                score=0.8,
            ),
            SimilarProduct(
                product_id="p4",
                product_name="Grey cardigan",
                product_type_name="Cardigan",
                product_group_name="Upper body",
                image_path=None,
                has_image=False,
                score=0.4,
            ),
        ],
    )
    search_response = SearchResultsResponse(
        query="black top",
        normalized_query="black top",
        k=2,
        retrieval_method="lexical_tfidf",
        scoring_method="cosine_similarity_over_l2_normalized_tfidf",
        indexed_fields=["product_name", "combined_text"],
        message=None,
        results=[
            SearchResult(
                product_id="p2",
                product_name="Black tank",
                product_type_name="Vest top",
                product_group_name="Upper body",
                colour_group_name="Black",
                department_name="Jersey Basic",
                image_path=None,
                has_image=False,
                score=0.7,
            ),
            SearchResult(
                product_id="p3",
                product_name="White shirt",
                product_type_name="Shirt",
                product_group_name="Upper body",
                colour_group_name="White",
                department_name="Shirts",
                image_path=None,
                has_image=False,
                score=0.35,
            ),
        ],
    )
    session_response = SessionRecommendationsResponse(
        query_session_id="sess_001",
        k=2,
        retrieval_method="session_multimodal_weighted_average",
        score_source="session_embedding_similarity",
        model_name="openai/clip-vit-base-patch32",
        fusion_alpha=0.6,
        max_recent_events=5,
        exclude_recent_products=True,
        usable_signal_count=1,
        ignored_event_count=0,
        unknown_product_ids=[],
        used_product_ids=["p_seen"],
        supported_signal_types=[
            "product_view",
            "detail_open",
            "similar_item_click",
            "like",
            "save",
        ],
        message=None,
        used_signals=[],
        results=[
            SessionRecommendation(
                product_id="p3",
                product_name="White shirt",
                product_type_name="Shirt",
                product_group_name="Upper body",
                colour_group_name="White",
                department_name="Shirts",
                image_path=None,
                has_image=False,
                score=0.95,
            ),
            SessionRecommendation(
                product_id="p5",
                product_name="Blue jeans",
                product_type_name="Trousers",
                product_group_name="Lower body",
                colour_group_name="Blue",
                department_name="Denim",
                image_path=None,
                has_image=False,
                score=0.5,
            ),
        ],
    )

    return CandidateBlendingService(
        collaborative_service=FakeCollaborativeService(collaborative_response),
        content_service=FakeContentService(content_response),
        search_service=FakeSearchService(search_response),
        session_service=FakeSessionService(session_response),
    )


def test_candidate_blending_merges_multiple_sources() -> None:
    service = build_service()

    response = service.blend_candidates(build_request())

    assert response.used_sources == ["collaborative", "content", "search", "session"]
    assert [candidate.product_id for candidate in response.results[:3]] == ["p1", "p2", "p3"]

    top_candidate = response.results[0]
    assert top_candidate.product_id == "p1"
    assert top_candidate.contributing_sources == ["collaborative", "content"]
    assert top_candidate.raw_source_scores == {
        "collaborative": 0.9,
        "content": 0.8,
    }
    assert top_candidate.normalized_source_scores == {
        "collaborative": 1.0,
        "content": 1.0,
    }
    assert top_candidate.blended_score == pytest.approx(1.9)


def test_candidate_blending_deduplicates_by_product_id_and_preserves_provenance() -> None:
    service = build_service()

    response = service.blend_candidates(
        build_request(
            query=None,
            search_k=1,
            session_events=[],
            like_events=[],
            save_events=[],
        )
    )

    product_ids = [candidate.product_id for candidate in response.results]

    assert product_ids.count("p1") == 1
    assert response.results[0].product_id == "p1"
    assert response.results[0].contributing_sources == ["collaborative", "content"]
    assert response.results[0].source_rank_positions == {
        "collaborative": 1,
        "content": 1,
    }
    assert response.results[0].source_weights == {
        "collaborative": 1.0,
        "content": 0.9,
    }


def test_candidate_blending_handles_empty_input_cleanly() -> None:
    service = build_service()

    response = service.blend_candidates(
        BlendedCandidatesRequest(
            blended_k=5,
        )
    )

    assert response.results == []
    assert response.used_sources == []
    assert response.message == (
        "No candidate sources were requested. Provide at least one of user_id, "
        "query, anchor_product_id, or session events."
    )
    assert all(summary.requested is False for summary in response.source_summaries)


def test_blend_endpoint_returns_expected_schema(monkeypatch) -> None:
    class FakeService:
        def blend_candidates(
            self,
            request: BlendedCandidatesRequest,
        ) -> BlendedCandidatesResponse:
            return BlendedCandidatesResponse(
                blended_k=request.blended_k,
                returned_candidate_count=1,
                normalization_strategy="min_max",
                dedup_key="product_id",
                used_sources=["search"],
                source_weights={
                    "collaborative": 1.0,
                    "session": 1.2,
                    "search": 1.3,
                    "content": 0.9,
                },
                message=None,
                source_summaries=[],
                results=[
                    BlendedCandidate(
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
                    )
                ],
            )

    monkeypatch.setattr(
        feed_candidates_route,
        "get_candidate_blending_service",
        lambda: FakeService(),
    )

    client = TestClient(app)
    response = client.post(
        "/candidates/blend",
        json={
            "query": "black top",
            "blended_k": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["blended_k"] == 5
    assert payload["used_sources"] == ["search"]
    assert payload["normalization_strategy"] == "min_max"
    assert payload["results"][0]["product_id"] == "p1"
