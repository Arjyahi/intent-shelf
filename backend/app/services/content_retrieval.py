import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from app.schemas.retrieval import SimilarProduct, SimilarProductsResponse


@dataclass(frozen=True)
class ContentRetrievalArtifactPaths:
    products_path: Path
    index_path: Path
    product_id_lookup_path: Path
    metadata_path: Path


def default_artifact_paths() -> ContentRetrievalArtifactPaths:
    repo_root = Path(__file__).resolve().parents[3]
    return ContentRetrievalArtifactPaths(
        products_path=repo_root / "data" / "processed" / "products.parquet",
        index_path=repo_root / "artifacts" / "indexes" / "product_multimodal.faiss",
        product_id_lookup_path=repo_root / "artifacts" / "indexes" / "product_id_lookup.json",
        metadata_path=repo_root / "artifacts" / "models" / "multimodal_embedding_metadata.json",
    )


class ContentRetrievalService:
    """
    Minimal multimodal content retrieval service for Phase 3.

    This service reads the saved FAISS index and lookup artifacts built by the
    offline scripts. It does not do collaborative retrieval, search retrieval,
    blending, or reranking yet.
    """

    def __init__(self, artifact_paths: ContentRetrievalArtifactPaths | None = None) -> None:
        self.artifact_paths = artifact_paths or default_artifact_paths()
        self._index: faiss.Index | None = None
        self._product_id_lookup: list[str] | None = None
        self._product_id_to_row: dict[str, int] | None = None
        self._products: pd.DataFrame | None = None
        self._metadata: dict[str, object] = {}

    def _load_artifacts(self) -> None:
        if self._index is not None:
            return

        missing_paths = [
            path
            for path in [
                self.artifact_paths.products_path,
                self.artifact_paths.index_path,
                self.artifact_paths.product_id_lookup_path,
            ]
            if not path.exists()
        ]
        if missing_paths:
            missing_labels = ", ".join(path.as_posix() for path in missing_paths)
            raise FileNotFoundError(
                "Missing multimodal retrieval artifact(s): "
                f"{missing_labels}. Run the Phase 3 retrieval scripts first."
            )

        self._index = faiss.read_index(str(self.artifact_paths.index_path))

        with self.artifact_paths.product_id_lookup_path.open("r", encoding="utf-8") as handle:
            self._product_id_lookup = json.load(handle)

        if self._index.ntotal != len(self._product_id_lookup):
            raise ValueError(
                "FAISS index size does not match product_id lookup length."
            )

        self._product_id_to_row = {
            product_id: row_index
            for row_index, product_id in enumerate(self._product_id_lookup)
        }

        self._products = pd.read_parquet(
            self.artifact_paths.products_path,
            columns=[
                "product_id",
                "product_name",
                "product_type_name",
                "product_group_name",
                "image_path",
                "has_image",
            ],
        ).set_index("product_id", drop=False)

        if self.artifact_paths.metadata_path.exists():
            with self.artifact_paths.metadata_path.open("r", encoding="utf-8") as handle:
                self._metadata = json.load(handle)

    def get_similar_products(self, product_id: str, k: int = 12) -> SimilarProductsResponse:
        self._load_artifacts()
        assert self._index is not None
        assert self._product_id_lookup is not None
        assert self._product_id_to_row is not None
        assert self._products is not None

        if product_id not in self._product_id_to_row:
            raise KeyError(f"Unknown product_id: {product_id}")

        query_row = self._product_id_to_row[product_id]
        query_vector = np.asarray(
            self._index.reconstruct(query_row),
            dtype=np.float32,
        ).reshape(1, -1)

        search_k = min(max(k + 1, 2), len(self._product_id_lookup))
        scores, row_indices = self._index.search(query_vector, search_k)

        results: list[SimilarProduct] = []
        for score, row_index in zip(scores[0], row_indices[0]):
            if row_index < 0:
                continue

            candidate_product_id = self._product_id_lookup[row_index]
            if candidate_product_id == product_id:
                continue
            if candidate_product_id not in self._products.index:
                continue

            candidate = self._products.loc[candidate_product_id]
            results.append(
                SimilarProduct(
                    product_id=candidate_product_id,
                    product_name=str(candidate["product_name"]),
                    product_type_name=candidate["product_type_name"],
                    product_group_name=candidate["product_group_name"],
                    image_path=candidate["image_path"],
                    has_image=bool(candidate["has_image"]),
                    score=float(score),
                )
            )

            if len(results) >= k:
                break

        return SimilarProductsResponse(
            query_product_id=product_id,
            k=k,
            model_name=self._metadata.get("model_name"),
            fusion_alpha=self._metadata.get("fusion_alpha"),
            results=results,
        )


@lru_cache(maxsize=1)
def get_content_retrieval_service() -> ContentRetrievalService:
    return ContentRetrievalService()
