import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.api.routes.recommendations as recommendations_route
from app.main import app
from app.schemas.retrieval import (
    CollaborativeRecommendation,
    CollaborativeRecommendationsResponse,
)
from app.services.collaborative_retrieval import (
    CollaborativeRetrievalArtifactPaths,
    CollaborativeRetrievalService,
)

pytest.importorskip("implicit")


def build_small_collaborative_artifacts(tmp_path) -> CollaborativeRetrievalArtifactPaths:
    from implicit.cpu.bpr import BayesianPersonalizedRanking
    from scipy.sparse import csr_matrix, save_npz

    products = pd.DataFrame(
        [
            {
                "product_id": "p1",
                "product_name": "Black tee",
                "product_type_name": "T-shirt",
                "product_group_name": "Upper body",
                "image_path": None,
                "has_image": False,
            },
            {
                "product_id": "p2",
                "product_name": "White tee",
                "product_type_name": "T-shirt",
                "product_group_name": "Upper body",
                "image_path": None,
                "has_image": False,
            },
            {
                "product_id": "p3",
                "product_name": "Blue jeans",
                "product_type_name": "Trousers",
                "product_group_name": "Lower body",
                "image_path": None,
                "has_image": False,
            },
        ]
    )
    products_path = tmp_path / "products.parquet"
    products.to_parquet(products_path, index=False)

    user_lookup = ["u1", "u2", "u3", "u4"]
    product_lookup = ["p1", "p2", "p3"]
    interaction_matrix = csr_matrix(
        [
            [2.0, 1.0, 0.0],
            [0.0, 1.0, 1.0],
            [0.0, 1.0, 1.0],
            [0.0, 1.0, 0.0],
        ],
        dtype="float32",
    )

    training_matrix = interaction_matrix.copy().tocsr()
    training_matrix.data[:] = 1.0

    model = BayesianPersonalizedRanking(
        factors=8,
        learning_rate=0.05,
        regularization=0.01,
        iterations=8,
        num_threads=1,
        random_state=42,
    )
    model.fit(training_matrix, show_progress=False)

    artifact_paths = CollaborativeRetrievalArtifactPaths(
        products_path=products_path,
        model_path=tmp_path / "implicit_model.npz",
        user_id_lookup_path=tmp_path / "user_id_lookup.json",
        product_id_lookup_path=tmp_path / "product_id_lookup_collaborative.json",
        user_item_matrix_path=tmp_path / "collaborative_user_item_matrix.npz",
        metadata_path=tmp_path / "collaborative_training_metadata.json",
    )

    model.save(str(artifact_paths.model_path))

    artifact_paths.user_id_lookup_path.write_text(json.dumps(user_lookup), encoding="utf-8")
    artifact_paths.product_id_lookup_path.write_text(
        json.dumps(product_lookup),
        encoding="utf-8",
    )
    save_npz(artifact_paths.user_item_matrix_path, interaction_matrix)
    artifact_paths.metadata_path.write_text(
        json.dumps({"model_name": "implicit", "model_type": "bpr", "loss": "bpr"}),
        encoding="utf-8",
    )
    return artifact_paths


def test_collaborative_retrieval_excludes_seen_items(tmp_path) -> None:
    artifact_paths = build_small_collaborative_artifacts(tmp_path)
    service = CollaborativeRetrievalService(artifact_paths=artifact_paths)

    response = service.get_recommendations(user_id="u1", k=3, exclude_seen_items=True)

    assert response.is_known_user is True
    assert response.score_source == "implicit_recommendation"
    assert len(response.results) == 1
    assert response.results[0].product_id == "p3"


def test_collaborative_retrieval_unknown_user_uses_popularity_fallback(tmp_path) -> None:
    artifact_paths = build_small_collaborative_artifacts(tmp_path)
    service = CollaborativeRetrievalService(artifact_paths=artifact_paths)

    response = service.get_recommendations(user_id="missing-user", k=2)

    assert response.is_known_user is False
    assert response.fallback_strategy == "global_popularity"
    assert response.score_source == "global_popularity"
    assert response.message is not None
    assert response.results[0].product_id == "p2"


def test_collaborative_retrieval_recovers_from_partial_loader_state(tmp_path) -> None:
    from implicit.cpu.bpr import BayesianPersonalizedRanking

    artifact_paths = build_small_collaborative_artifacts(tmp_path)
    service = CollaborativeRetrievalService(artifact_paths=artifact_paths)

    service._model = BayesianPersonalizedRanking.load(str(artifact_paths.model_path))
    service._user_id_lookup = None
    service._product_id_lookup = None
    service._user_id_to_row = None
    service._products = None
    service._interaction_matrix = None
    service._item_popularity = None

    response = service.get_recommendations(user_id="missing-user", k=2)

    assert response.is_known_user is False
    assert response.fallback_strategy == "global_popularity"


def test_collaborative_endpoint_returns_expected_schema(monkeypatch) -> None:
    class FakeService:
        def get_recommendations(
            self,
            user_id: str,
            k: int = 20,
            exclude_seen_items: bool = True,
        ) -> CollaborativeRecommendationsResponse:
            return CollaborativeRecommendationsResponse(
                query_user_id=user_id,
                k=k,
                model_name="implicit",
                model_loss="bpr",
                exclude_seen_items=exclude_seen_items,
                is_known_user=True,
                score_source="implicit_recommendation",
                fallback_strategy=None,
                message=None,
                results=[
                    CollaborativeRecommendation(
                        product_id="p3",
                        product_name="Blue jeans",
                        product_type_name="Trousers",
                        product_group_name="Lower body",
                        image_path=None,
                        has_image=False,
                        score=0.87,
                    )
                ],
            )

    monkeypatch.setattr(
        recommendations_route,
        "get_collaborative_retrieval_service",
        lambda: FakeService(),
    )

    client = TestClient(app)
    response = client.get(
        "/users/u1/recommendations/collaborative",
        params={"k": 1, "exclude_seen_items": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_user_id"] == "u1"
    assert payload["k"] == 1
    assert payload["is_known_user"] is True
    assert payload["results"][0]["product_id"] == "p3"
