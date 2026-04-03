import json

import faiss
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import app.api.routes.products as products_route
from app.main import app
from app.schemas.retrieval import SimilarProduct, SimilarProductsResponse
from app.services.content_retrieval import (
    ContentRetrievalArtifactPaths,
    ContentRetrievalService,
)


def test_content_retrieval_excludes_query_item(tmp_path) -> None:
    products = pd.DataFrame(
        [
            {
                "product_id": "p1",
                "product_name": "Black top",
                "product_type_name": "Top",
                "product_group_name": "Upper body",
                "image_path": "data/raw/images/example/p1.jpg",
                "has_image": True,
            },
            {
                "product_id": "p2",
                "product_name": "Black tank",
                "product_type_name": "Top",
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

    embeddings = np.array(
        [
            [1.0, 0.0],
            [0.95, 0.05],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    index_path = tmp_path / "product_multimodal.faiss"
    faiss.write_index(index, str(index_path))

    lookup_path = tmp_path / "product_id_lookup.json"
    lookup_path.write_text(json.dumps(["p1", "p2", "p3"]), encoding="utf-8")

    metadata_path = tmp_path / "multimodal_embedding_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_name": "openai/clip-vit-base-patch32",
                "fusion_alpha": 0.6,
            }
        ),
        encoding="utf-8",
    )

    service = ContentRetrievalService(
        artifact_paths=ContentRetrievalArtifactPaths(
            products_path=products_path,
            index_path=index_path,
            product_id_lookup_path=lookup_path,
            metadata_path=metadata_path,
        )
    )

    response = service.get_similar_products(product_id="p1", k=2)

    assert response.query_product_id == "p1"
    assert len(response.results) == 2
    assert all(item.product_id != "p1" for item in response.results)
    assert response.results[0].product_id == "p2"


def test_similar_products_endpoint_returns_expected_schema(monkeypatch) -> None:
    class FakeService:
        def get_similar_products(self, product_id: str, k: int = 12) -> SimilarProductsResponse:
            return SimilarProductsResponse(
                query_product_id=product_id,
                k=k,
                model_name="openai/clip-vit-base-patch32",
                fusion_alpha=0.6,
                results=[
                    SimilarProduct(
                        product_id="p2",
                        product_name="Black tank",
                        product_type_name="Top",
                        product_group_name="Upper body",
                        image_path=None,
                        has_image=False,
                        score=0.91,
                    )
                ],
            )

    monkeypatch.setattr(
        products_route,
        "get_content_retrieval_service",
        lambda: FakeService(),
    )

    client = TestClient(app)
    response = client.get("/products/p1/similar", params={"k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_product_id"] == "p1"
    assert payload["k"] == 1
    assert payload["results"][0]["product_id"] == "p2"
