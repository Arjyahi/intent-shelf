import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, load_npz

try:
    from implicit.cpu.bpr import BayesianPersonalizedRanking
except ImportError as exc:
    BayesianPersonalizedRanking = Any  # type: ignore[assignment]
    IMPLICIT_IMPORT_ERROR = exc
else:
    IMPLICIT_IMPORT_ERROR = None

from app.schemas.retrieval import (
    CollaborativeRecommendation,
    CollaborativeRecommendationsResponse,
)


def require_implicit() -> None:
    if IMPLICIT_IMPORT_ERROR is not None:
        raise ImportError(
            "implicit is required for Phase 4 collaborative retrieval. "
            "Install backend/requirements.txt before using this endpoint."
        ) from IMPLICIT_IMPORT_ERROR


@dataclass(frozen=True)
class CollaborativeRetrievalArtifactPaths:
    products_path: Path
    model_path: Path
    user_id_lookup_path: Path
    product_id_lookup_path: Path
    user_item_matrix_path: Path
    metadata_path: Path


def default_artifact_paths() -> CollaborativeRetrievalArtifactPaths:
    repo_root = Path(__file__).resolve().parents[3]
    return CollaborativeRetrievalArtifactPaths(
        products_path=repo_root / "data" / "processed" / "products.parquet",
        model_path=repo_root / "artifacts" / "models" / "implicit_model.npz",
        user_id_lookup_path=repo_root / "artifacts" / "indexes" / "user_id_lookup.json",
        product_id_lookup_path=repo_root / "artifacts" / "indexes" / "product_id_lookup_collaborative.json",
        user_item_matrix_path=repo_root / "artifacts" / "indexes" / "collaborative_user_item_matrix.npz",
        metadata_path=repo_root / "artifacts" / "models" / "collaborative_training_metadata.json",
    )


class CollaborativeRetrievalService:
    """
    Minimal collaborative retrieval service for Phase 4.

    This service only reads collaborative model artifacts built offline from
    interactions_train.parquet. It does not do content blending, search
    retrieval, session retrieval, or reranking yet.
    """

    def __init__(self, artifact_paths: CollaborativeRetrievalArtifactPaths | None = None) -> None:
        self.artifact_paths = artifact_paths or default_artifact_paths()
        self._artifact_lock = Lock()
        self._model: BayesianPersonalizedRanking | None = None
        self._user_id_lookup: list[str] | None = None
        self._product_id_lookup: list[str] | None = None
        self._user_id_to_row: dict[str, int] | None = None
        self._products: pd.DataFrame | None = None
        self._interaction_matrix: csr_matrix | None = None
        self._item_popularity: np.ndarray | None = None
        self._metadata: dict[str, object] = {}

    def _artifacts_loaded(self) -> bool:
        return all(
            value is not None
            for value in [
                self._model,
                self._user_id_lookup,
                self._product_id_lookup,
                self._user_id_to_row,
                self._products,
                self._interaction_matrix,
                self._item_popularity,
            ]
        )

    def _load_artifacts(self) -> None:
        if self._artifacts_loaded():
            return

        with self._artifact_lock:
            if self._artifacts_loaded():
                return

            require_implicit()

            missing_paths = [
                path
                for path in [
                    self.artifact_paths.products_path,
                    self.artifact_paths.model_path,
                    self.artifact_paths.user_id_lookup_path,
                    self.artifact_paths.product_id_lookup_path,
                    self.artifact_paths.user_item_matrix_path,
                ]
                if not path.exists()
            ]
            if missing_paths:
                missing_labels = ", ".join(path.as_posix() for path in missing_paths)
                raise FileNotFoundError(
                    "Missing collaborative retrieval artifact(s): "
                    f"{missing_labels}. Run the Phase 4 collaborative training script first."
                )

            model = BayesianPersonalizedRanking.load(str(self.artifact_paths.model_path))

            with self.artifact_paths.user_id_lookup_path.open("r", encoding="utf-8") as handle:
                user_id_lookup = json.load(handle)

            with self.artifact_paths.product_id_lookup_path.open("r", encoding="utf-8") as handle:
                product_id_lookup = json.load(handle)

            interaction_matrix = load_npz(self.artifact_paths.user_item_matrix_path).tocsr()
            item_popularity = np.asarray(interaction_matrix.sum(axis=0)).ravel().astype(np.float32)

            user_id_to_row = {
                user_id: row_index
                for row_index, user_id in enumerate(user_id_lookup)
            }

            products = pd.read_parquet(
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

            metadata: dict[str, object] = {}
            if self.artifact_paths.metadata_path.exists():
                with self.artifact_paths.metadata_path.open("r", encoding="utf-8") as handle:
                    metadata = json.load(handle)

            if interaction_matrix.shape != (
                len(user_id_lookup),
                len(product_id_lookup),
            ):
                raise ValueError(
                    "Saved collaborative user-item matrix shape does not match the lookup files."
                )

            if model.user_factors.shape[0] != len(user_id_lookup):
                raise ValueError("implicit user factors do not match the user_id lookup length.")

            if model.item_factors.shape[0] != len(product_id_lookup):
                raise ValueError("implicit item factors do not match the product_id lookup length.")

            self._model = model
            self._user_id_lookup = user_id_lookup
            self._product_id_lookup = product_id_lookup
            self._user_id_to_row = user_id_to_row
            self._interaction_matrix = interaction_matrix
            self._item_popularity = item_popularity
            self._products = products
            self._metadata = metadata

    @staticmethod
    def _select_top_item_indices(scores: np.ndarray, k: int) -> np.ndarray:
        valid_mask = np.isfinite(scores)
        valid_count = int(valid_mask.sum())
        if valid_count == 0:
            return np.array([], dtype=np.int32)

        candidate_count = min(k, valid_count)
        if candidate_count >= len(scores):
            ranked_indices = np.argsort(scores)[::-1]
            return ranked_indices[:candidate_count].astype(np.int32)

        top_indices = np.argpartition(scores, -candidate_count)[-candidate_count:]
        ranked_top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        return ranked_top_indices.astype(np.int32)

    def _build_results(
        self,
        item_indices: np.ndarray,
        scores: np.ndarray,
    ) -> list[CollaborativeRecommendation]:
        assert self._product_id_lookup is not None
        assert self._products is not None

        results: list[CollaborativeRecommendation] = []
        for item_index, score in zip(item_indices, scores):
            if int(item_index) < 0:
                continue
            if not np.isfinite(score):
                continue
            if float(score) <= (np.finfo(np.float32).min / 2.0):
                continue

            product_id = self._product_id_lookup[int(item_index)]
            if product_id not in self._products.index:
                continue

            product = self._products.loc[product_id]
            results.append(
                CollaborativeRecommendation(
                    product_id=product_id,
                    product_name=str(product["product_name"]),
                    product_type_name=product["product_type_name"],
                    product_group_name=product["product_group_name"],
                    image_path=product["image_path"],
                    has_image=bool(product["has_image"]),
                    score=float(score),
                )
            )
        return results

    def _popularity_fallback(
        self,
        user_id: str,
        k: int,
    ) -> CollaborativeRecommendationsResponse:
        assert self._item_popularity is not None

        ranked_indices = self._select_top_item_indices(self._item_popularity.copy(), k)
        ranked_scores = self._item_popularity[ranked_indices]
        results = self._build_results(ranked_indices, ranked_scores)
        return CollaborativeRecommendationsResponse(
            query_user_id=user_id,
            k=k,
            model_name=str(self._metadata.get("model_name", "implicit")),
            model_loss=self._metadata.get("model_type", self._metadata.get("loss")),
            exclude_seen_items=False,
            is_known_user=False,
            score_source="global_popularity",
            fallback_strategy="global_popularity",
            message=(
                "Unknown user_id. Returning a non-personalized popularity fallback "
                "from the training interactions."
            ),
            results=results,
        )

    def get_recommendations(
        self,
        user_id: str,
        k: int = 20,
        exclude_seen_items: bool = True,
    ) -> CollaborativeRecommendationsResponse:
        self._load_artifacts()
        assert self._model is not None
        assert self._user_id_lookup is not None
        assert self._user_id_to_row is not None
        assert self._product_id_lookup is not None
        assert self._interaction_matrix is not None

        if user_id not in self._user_id_to_row:
            return self._popularity_fallback(user_id=user_id, k=k)

        user_row = self._user_id_to_row[user_id]
        max_recommendations = min(k, len(self._product_id_lookup))
        item_indices, scores = self._model.recommend(
            userid=user_row,
            user_items=self._interaction_matrix[user_row],
            N=max_recommendations,
            filter_already_liked_items=exclude_seen_items,
        )

        item_indices = np.asarray(item_indices, dtype=np.int32)
        scores = np.asarray(scores, dtype=np.float32)
        results = self._build_results(item_indices, scores)

        message = None
        if not results:
            message = "Known user has no unseen collaborative candidates with the current artifacts."

        return CollaborativeRecommendationsResponse(
            query_user_id=user_id,
            k=k,
            model_name=str(self._metadata.get("model_name", "implicit")),
            model_loss=self._metadata.get("model_type", self._metadata.get("loss")),
            exclude_seen_items=exclude_seen_items,
            is_known_user=True,
            score_source="implicit_recommendation",
            fallback_strategy=None,
            message=message,
            results=results,
        )


@lru_cache(maxsize=1)
def get_collaborative_retrieval_service() -> CollaborativeRetrievalService:
    return CollaborativeRetrievalService()
