import json
import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, load_npz
from sklearn.utils.extmath import safe_sparse_dot

from app.schemas.retrieval import SearchResult, SearchResultsResponse


@dataclass(frozen=True)
class SearchRetrievalArtifactPaths:
    products_path: Path
    vectorizer_path: Path
    metadata_path: Path
    tfidf_matrix_path: Path
    product_id_lookup_path: Path


def default_artifact_paths() -> SearchRetrievalArtifactPaths:
    repo_root = Path(__file__).resolve().parents[3]
    return SearchRetrievalArtifactPaths(
        products_path=repo_root / "data" / "processed" / "products.parquet",
        vectorizer_path=repo_root / "artifacts" / "models" / "product_search_vectorizer.pkl",
        metadata_path=repo_root / "artifacts" / "models" / "search_index_metadata.json",
        tfidf_matrix_path=repo_root / "artifacts" / "indexes" / "product_search_tfidf_matrix.npz",
        product_id_lookup_path=repo_root / "artifacts" / "indexes" / "product_search_product_id_lookup.json",
    )


class SearchRetrievalService:
    """
    Minimal lexical search retrieval service for Phase 5.

    This service loads a saved TF-IDF vectorizer and sparse product matrix built
    offline from products.parquet. It does not do personalization, blending,
    session retrieval, or reranking yet.
    """

    def __init__(self, artifact_paths: SearchRetrievalArtifactPaths | None = None) -> None:
        self.artifact_paths = artifact_paths or default_artifact_paths()
        self._vectorizer = None
        self._tfidf_matrix: csr_matrix | None = None
        self._product_id_lookup: list[str] | None = None
        self._products: pd.DataFrame | None = None
        self._metadata: dict[str, object] = {}

    def _load_artifacts(self) -> None:
        if self._vectorizer is not None:
            return

        missing_paths = [
            path
            for path in [
                self.artifact_paths.products_path,
                self.artifact_paths.vectorizer_path,
                self.artifact_paths.metadata_path,
                self.artifact_paths.tfidf_matrix_path,
                self.artifact_paths.product_id_lookup_path,
            ]
            if not path.exists()
        ]
        if missing_paths:
            missing_labels = ", ".join(path.as_posix() for path in missing_paths)
            raise FileNotFoundError(
                "Missing search retrieval artifact(s): "
                f"{missing_labels}. Run the Phase 5 search index build script first."
            )

        with self.artifact_paths.vectorizer_path.open("rb") as handle:
            self._vectorizer = pickle.load(handle)

        self._tfidf_matrix = load_npz(self.artifact_paths.tfidf_matrix_path).tocsr()

        with self.artifact_paths.product_id_lookup_path.open("r", encoding="utf-8") as handle:
            self._product_id_lookup = json.load(handle)

        with self.artifact_paths.metadata_path.open("r", encoding="utf-8") as handle:
            self._metadata = json.load(handle)

        if self._tfidf_matrix.shape[0] != len(self._product_id_lookup):
            raise ValueError(
                "Saved TF-IDF matrix row count does not match the product_id lookup length."
            )

        self._products = pd.read_parquet(
            self.artifact_paths.products_path,
            columns=[
                "product_id",
                "product_name",
                "product_type_name",
                "product_group_name",
                "colour_group_name",
                "department_name",
                "image_path",
                "has_image",
            ],
        )
        self._products["product_id"] = self._products["product_id"].astype(str)
        self._products = self._products.set_index("product_id", drop=False)

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(query.split())

    @staticmethod
    def _select_top_product_indices(scores: np.ndarray, k: int) -> np.ndarray:
        positive_indices = np.flatnonzero(scores > 0.0)
        if len(positive_indices) == 0:
            return np.array([], dtype=np.int32)

        candidate_count = min(k, len(positive_indices))
        if candidate_count >= len(positive_indices):
            ranked_indices = positive_indices[np.argsort(scores[positive_indices])[::-1]]
            return ranked_indices[:candidate_count].astype(np.int32)

        top_local_indices = np.argpartition(
            scores[positive_indices],
            -candidate_count,
        )[-candidate_count:]
        top_indices = positive_indices[top_local_indices]
        ranked_top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        return ranked_top_indices.astype(np.int32)

    def _empty_response(
        self,
        query: str,
        normalized_query: str,
        k: int,
        message: str,
    ) -> SearchResultsResponse:
        return SearchResultsResponse(
            query=query,
            normalized_query=normalized_query,
            k=k,
            retrieval_method=self._metadata.get("retrieval_method"),
            scoring_method=self._metadata.get("scoring_method"),
            indexed_fields=list(self._metadata.get("indexed_fields", [])),
            message=message,
            results=[],
        )

    def search(self, query: str, k: int = 20) -> SearchResultsResponse:
        self._load_artifacts()
        assert self._vectorizer is not None
        assert self._tfidf_matrix is not None
        assert self._product_id_lookup is not None
        assert self._products is not None

        normalized_query = self._normalize_query(query)
        if not normalized_query:
            return self._empty_response(
                query=query,
                normalized_query=normalized_query,
                k=k,
                message="Empty or whitespace-only query. Returning no search results.",
            )

        query_vector = self._vectorizer.transform([normalized_query])
        if query_vector.nnz == 0:
            return self._empty_response(
                query=query,
                normalized_query=normalized_query,
                k=k,
                message=(
                    "Query terms are outside the current lexical vocabulary. "
                    "Returning no search results."
                ),
            )

        scores = safe_sparse_dot(
            query_vector,
            self._tfidf_matrix.T,
            dense_output=True,
        )
        score_array = np.asarray(scores).ravel().astype(np.float32)
        ranked_indices = self._select_top_product_indices(score_array, k=k)

        if len(ranked_indices) == 0:
            return self._empty_response(
                query=query,
                normalized_query=normalized_query,
                k=k,
                message="No products matched the current lexical query.",
            )

        results: list[SearchResult] = []
        for row_index in ranked_indices:
            product_id = self._product_id_lookup[int(row_index)]
            if product_id not in self._products.index:
                continue

            product = self._products.loc[product_id]
            results.append(
                SearchResult(
                    product_id=product_id,
                    product_name=str(product["product_name"]),
                    product_type_name=product["product_type_name"],
                    product_group_name=product["product_group_name"],
                    colour_group_name=product["colour_group_name"],
                    department_name=product["department_name"],
                    image_path=product["image_path"],
                    has_image=bool(product["has_image"]),
                    score=float(score_array[int(row_index)]),
                )
            )

        message = None
        if not results:
            message = "Matched rows were missing from products.parquet metadata."

        return SearchResultsResponse(
            query=query,
            normalized_query=normalized_query,
            k=k,
            retrieval_method=self._metadata.get("retrieval_method"),
            scoring_method=self._metadata.get("scoring_method"),
            indexed_fields=list(self._metadata.get("indexed_fields", [])),
            message=message,
            results=results,
        )


@lru_cache(maxsize=1)
def get_search_retrieval_service() -> SearchRetrievalService:
    return SearchRetrievalService()
