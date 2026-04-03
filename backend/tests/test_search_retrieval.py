import json
import pickle

import pandas as pd
from fastapi.testclient import TestClient
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

import app.api.routes.search as search_route
from app.main import app
from app.schemas.retrieval import SearchResult, SearchResultsResponse
from app.services.search_retrieval import SearchRetrievalArtifactPaths, SearchRetrievalService


def build_small_search_artifacts(tmp_path) -> SearchRetrievalArtifactPaths:
    products = pd.DataFrame(
        [
            {
                "product_id": "p1",
                "product_name": "Black summer top",
                "product_type_name": "Top",
                "product_group_name": "Upper body",
                "colour_group_name": "Black",
                "department_name": "Jersey Basic",
                "image_path": None,
                "has_image": False,
                "combined_text": (
                    "Black summer top | Top | Upper body | Black | Jersey Basic | "
                    "Lightweight sleeveless top for warm weather."
                ),
            },
            {
                "product_id": "p2",
                "product_name": "Blue denim jeans",
                "product_type_name": "Trousers",
                "product_group_name": "Lower body",
                "colour_group_name": "Blue",
                "department_name": "Denim",
                "image_path": None,
                "has_image": False,
                "combined_text": (
                    "Blue denim jeans | Trousers | Lower body | Blue | Denim | "
                    "Straight-leg denim jeans."
                ),
            },
            {
                "product_id": "p3",
                "product_name": "White cotton shirt",
                "product_type_name": "Shirt",
                "product_group_name": "Upper body",
                "colour_group_name": "White",
                "department_name": "Shirts",
                "image_path": None,
                "has_image": False,
                "combined_text": (
                    "White cotton shirt | Shirt | Upper body | White | Shirts | "
                    "Classic button-up shirt."
                ),
            },
        ]
    )
    products_path = tmp_path / "products.parquet"
    products.to_parquet(products_path, index=False)

    documents = [
        (
            "Black summer top Black summer top Black summer top "
            "Top Top Upper body Upper body Black Black Jersey Basic "
            "Black summer top | Top | Upper body | Black | Jersey Basic | "
            "Lightweight sleeveless top for warm weather."
        ),
        (
            "Blue denim jeans Blue denim jeans Blue denim jeans "
            "Trousers Trousers Lower body Lower body Blue Blue Denim "
            "Blue denim jeans | Trousers | Lower body | Blue | Denim | "
            "Straight-leg denim jeans."
        ),
        (
            "White cotton shirt White cotton shirt White cotton shirt "
            "Shirt Shirt Upper body Upper body White White Shirts "
            "White cotton shirt | Shirt | Upper body | White | Shirts | "
            "Classic button-up shirt."
        ),
    ]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        norm="l2",
    )
    tfidf_matrix = vectorizer.fit_transform(documents).tocsr()

    artifact_paths = SearchRetrievalArtifactPaths(
        products_path=products_path,
        vectorizer_path=tmp_path / "product_search_vectorizer.pkl",
        metadata_path=tmp_path / "search_index_metadata.json",
        tfidf_matrix_path=tmp_path / "product_search_tfidf_matrix.npz",
        product_id_lookup_path=tmp_path / "product_search_product_id_lookup.json",
    )

    with artifact_paths.vectorizer_path.open("wb") as handle:
        pickle.dump(vectorizer, handle)

    save_npz(artifact_paths.tfidf_matrix_path, tfidf_matrix)
    artifact_paths.product_id_lookup_path.write_text(
        json.dumps(["p1", "p2", "p3"]),
        encoding="utf-8",
    )
    artifact_paths.metadata_path.write_text(
        json.dumps(
            {
                "retrieval_method": "lexical_tfidf",
                "scoring_method": "cosine_similarity_over_l2_normalized_tfidf",
                "indexed_fields": [
                    "product_name",
                    "product_type_name",
                    "product_group_name",
                    "colour_group_name",
                    "department_name",
                    "combined_text",
                ],
            }
        ),
        encoding="utf-8",
    )

    return artifact_paths


def test_search_retrieval_handles_empty_query(tmp_path) -> None:
    artifact_paths = build_small_search_artifacts(tmp_path)
    service = SearchRetrievalService(artifact_paths=artifact_paths)

    response = service.search(query="   ", k=5)

    assert response.normalized_query == ""
    assert response.message == "Empty or whitespace-only query. Returning no search results."
    assert response.results == []


def test_search_retrieval_returns_ranked_results(tmp_path) -> None:
    artifact_paths = build_small_search_artifacts(tmp_path)
    service = SearchRetrievalService(artifact_paths=artifact_paths)

    response = service.search(query="black summer top", k=2)

    assert response.query == "black summer top"
    assert response.retrieval_method == "lexical_tfidf"
    assert len(response.results) >= 1
    assert response.results[0].product_id == "p1"
    assert response.results[0].score > 0.0


def test_search_endpoint_returns_expected_schema(monkeypatch) -> None:
    class FakeService:
        def search(self, query: str, k: int = 20) -> SearchResultsResponse:
            return SearchResultsResponse(
                query=query,
                normalized_query="black top",
                k=k,
                retrieval_method="lexical_tfidf",
                scoring_method="cosine_similarity_over_l2_normalized_tfidf",
                indexed_fields=["product_name", "combined_text"],
                message=None,
                results=[
                    SearchResult(
                        product_id="p1",
                        product_name="Black summer top",
                        product_type_name="Top",
                        product_group_name="Upper body",
                        colour_group_name="Black",
                        department_name="Jersey Basic",
                        image_path=None,
                        has_image=False,
                        score=0.93,
                    )
                ],
            )

    monkeypatch.setattr(
        search_route,
        "get_search_retrieval_service",
        lambda: FakeService(),
    )

    client = TestClient(app)
    response = client.get("/search", params={"query": "black top", "k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "black top"
    assert payload["k"] == 1
    assert payload["results"][0]["product_id"] == "p1"
