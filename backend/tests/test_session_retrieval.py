import json
from datetime import datetime, timezone

import faiss
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import app.api.routes.session as session_route
from app.main import app
from app.schemas.common import SessionEventType, SurfaceName
from app.schemas.events import LikeEvent, Session, SessionEvent
from app.schemas.retrieval import (
    SessionRecommendation,
    SessionRecommendationsRequest,
    SessionRecommendationsResponse,
)
from app.services.session_retrieval import (
    SessionRetrievalArtifactPaths,
    SessionRetrievalConfig,
    SessionRetrievalService,
)


def build_small_session_artifacts(tmp_path) -> SessionRetrievalConfig:
    products = pd.DataFrame(
        [
            {
                "product_id": "p1",
                "product_name": "Black tee",
                "product_type_name": "T-shirt",
                "product_group_name": "Upper body",
                "colour_group_name": "Black",
                "department_name": "Jersey Basic",
                "image_path": None,
                "has_image": False,
            },
            {
                "product_id": "p2",
                "product_name": "Black tank",
                "product_type_name": "Vest top",
                "product_group_name": "Upper body",
                "colour_group_name": "Black",
                "department_name": "Jersey Basic",
                "image_path": None,
                "has_image": False,
            },
            {
                "product_id": "p3",
                "product_name": "Blue jeans",
                "product_type_name": "Trousers",
                "product_group_name": "Lower body",
                "colour_group_name": "Blue",
                "department_name": "Denim",
                "image_path": None,
                "has_image": False,
            },
        ]
    )
    products_path = tmp_path / "products.parquet"
    products.to_parquet(products_path, index=False)

    embeddings = np.array(
        [
            [1.0, 0.0],
            [0.98, 0.02],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    index_path = tmp_path / "product_multimodal.faiss"
    faiss.write_index(index, str(index_path))

    product_lookup_path = tmp_path / "product_id_lookup.json"
    product_lookup_path.write_text(json.dumps(["p1", "p2", "p3"]), encoding="utf-8")

    metadata_path = tmp_path / "multimodal_embedding_metadata.json"
    metadata_path.write_text(
        json.dumps({"model_name": "openai/clip-vit-base-patch32", "fusion_alpha": 0.6}),
        encoding="utf-8",
    )

    artifact_paths = SessionRetrievalArtifactPaths(
        products_path=products_path,
        index_path=index_path,
        product_id_lookup_path=product_lookup_path,
        metadata_path=metadata_path,
    )
    return SessionRetrievalConfig(artifact_paths=artifact_paths, max_recent_events=5)


def build_request(
    session_events: list[SessionEvent] | None = None,
    like_events: list[LikeEvent] | None = None,
) -> SessionRecommendationsRequest:
    session = Session(
        session_id="sess_test_001",
        user_id="user_test_001",
        session_start=datetime(2020, 9, 20, 12, 0, tzinfo=timezone.utc),
        entry_surface=SurfaceName.HOME_FEED,
    )
    return SessionRecommendationsRequest(
        session=session,
        session_events=session_events or [],
        like_events=like_events or [],
        save_events=[],
        k=2,
        max_recent_events=5,
        exclude_recent_products=True,
    )


def test_session_retrieval_handles_empty_request(tmp_path) -> None:
    config = build_small_session_artifacts(tmp_path)
    service = SessionRetrievalService(config=config)

    response = service.get_recommendations(build_request())

    assert response.results == []
    assert response.message == (
        "Session request contains no recent events. Returning no session-based candidates."
    )
    assert response.usable_signal_count == 0


def test_session_retrieval_handles_no_supported_product_events(tmp_path) -> None:
    config = build_small_session_artifacts(tmp_path)
    service = SessionRetrievalService(config=config)

    request = build_request(
        session_events=[
            SessionEvent(
                event_id="sevt_001",
                session_id="sess_test_001",
                user_id="user_test_001",
                event_timestamp=datetime(2020, 9, 20, 12, 1, tzinfo=timezone.utc),
                event_type=SessionEventType.CLICK,
                source_surface=SurfaceName.HOME_FEED,
                product_id="p1",
            )
        ]
    )

    response = service.get_recommendations(request)

    assert response.results == []
    assert response.ignored_event_count == 1
    assert response.message == (
        "Session request has no supported product-linked events. "
        "Returning no session-based candidates."
    )


def test_session_retrieval_excludes_recent_products(tmp_path) -> None:
    config = build_small_session_artifacts(tmp_path)
    service = SessionRetrievalService(config=config)

    request = build_request(
        session_events=[
            SessionEvent(
                event_id="sevt_002",
                session_id="sess_test_001",
                user_id="user_test_001",
                event_timestamp=datetime(2020, 9, 20, 12, 1, tzinfo=timezone.utc),
                event_type=SessionEventType.DETAIL_OPEN,
                source_surface=SurfaceName.PRODUCT_DETAIL,
                product_id="p1",
            )
        ]
    )

    response = service.get_recommendations(request)

    assert response.usable_signal_count == 1
    assert response.used_product_ids == ["p1"]
    assert response.results[0].product_id == "p2"
    assert all(result.product_id != "p1" for result in response.results)


def test_session_retrieval_handles_unknown_product_ids(tmp_path) -> None:
    config = build_small_session_artifacts(tmp_path)
    service = SessionRetrievalService(config=config)

    request = build_request(
        session_events=[
            SessionEvent(
                event_id="sevt_003",
                session_id="sess_test_001",
                user_id="user_test_001",
                event_timestamp=datetime(2020, 9, 20, 12, 1, tzinfo=timezone.utc),
                event_type=SessionEventType.DETAIL_OPEN,
                source_surface=SurfaceName.PRODUCT_DETAIL,
                product_id="missing_product",
            )
        ]
    )

    response = service.get_recommendations(request)

    assert response.results == []
    assert response.unknown_product_ids == ["missing_product"]
    assert response.message == (
        "No usable recent session products matched the multimodal index. "
        "Returning no session-based candidates."
    )


def test_session_endpoint_returns_expected_schema(monkeypatch) -> None:
    class FakeService:
        def get_recommendations(
            self,
            request: SessionRecommendationsRequest,
        ) -> SessionRecommendationsResponse:
            return SessionRecommendationsResponse(
                query_session_id=request.session.session_id if request.session else None,
                k=request.k,
                retrieval_method="session_multimodal_weighted_average",
                score_source="session_embedding_similarity",
                model_name="openai/clip-vit-base-patch32",
                fusion_alpha=0.6,
                max_recent_events=request.max_recent_events or 5,
                exclude_recent_products=request.exclude_recent_products,
                usable_signal_count=1,
                ignored_event_count=0,
                unknown_product_ids=[],
                used_product_ids=["p1"],
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
                        product_id="p2",
                        product_name="Black tank",
                        product_type_name="Vest top",
                        product_group_name="Upper body",
                        colour_group_name="Black",
                        department_name="Jersey Basic",
                        image_path=None,
                        has_image=False,
                        score=0.91,
                    )
                ],
            )

    monkeypatch.setattr(
        session_route,
        "get_session_retrieval_service",
        lambda: FakeService(),
    )

    client = TestClient(app)
    response = client.post(
        "/sessions/recommendations",
        json=build_request().model_dump(mode="json"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_session_id"] == "sess_test_001"
    assert payload["k"] == 2
    assert payload["results"][0]["product_id"] == "p2"
