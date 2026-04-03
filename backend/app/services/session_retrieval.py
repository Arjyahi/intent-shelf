import json
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from app.schemas.common import SessionEventType
from app.schemas.retrieval import (
    SessionRecommendation,
    SessionRecommendationsRequest,
    SessionRecommendationsResponse,
    SessionSignalSummary,
)
from app.services.content_retrieval import default_artifact_paths as default_content_artifact_paths

DEFAULT_MAX_RECENT_EVENTS = 5
DEFAULT_TOP_K = 20
DEFAULT_EXCLUDE_RECENT_PRODUCTS = True

DEFAULT_SESSION_EVENT_WEIGHTS = {
    SessionEventType.PRODUCT_VIEW.value: 1.0,
    SessionEventType.DETAIL_OPEN.value: 2.0,
    SessionEventType.SIMILAR_ITEM_CLICK.value: 2.5,
}

DEFAULT_ACTION_WEIGHTS = {
    "like": 3.0,
    "save": 3.0,
}


@dataclass(frozen=True)
class SessionRetrievalArtifactPaths:
    products_path: Path
    index_path: Path
    product_id_lookup_path: Path
    metadata_path: Path


def default_artifact_paths() -> SessionRetrievalArtifactPaths:
    content_paths = default_content_artifact_paths()
    return SessionRetrievalArtifactPaths(
        products_path=content_paths.products_path,
        index_path=content_paths.index_path,
        product_id_lookup_path=content_paths.product_id_lookup_path,
        metadata_path=content_paths.metadata_path,
    )


@dataclass(frozen=True)
class SessionRetrievalConfig:
    max_recent_events: int = DEFAULT_MAX_RECENT_EVENTS
    top_k_default: int = DEFAULT_TOP_K
    exclude_recent_products_default: bool = DEFAULT_EXCLUDE_RECENT_PRODUCTS
    session_event_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_SESSION_EVENT_WEIGHTS)
    )
    action_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_ACTION_WEIGHTS))
    artifact_paths: SessionRetrievalArtifactPaths = field(default_factory=default_artifact_paths)


def default_session_config() -> SessionRetrievalConfig:
    return SessionRetrievalConfig()


@dataclass(frozen=True)
class SessionSignal:
    event_id: str
    signal_type: str
    product_id: str
    event_timestamp: datetime
    weight: float


def l2_normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise ValueError("Cannot normalize a zero-length session vector.")
    return vector / norm


def unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered_values.append(value)
    return ordered_values


class SessionRetrievalService:
    """
    Minimal session retrieval service for Phase 6.

    This service reuses the Phase 3 multimodal FAISS index as the retrieval
    space. It builds a session embedding from recent runtime product-linked
    events and returns nearest products in that same embedding space.
    """

    def __init__(self, config: SessionRetrievalConfig | None = None) -> None:
        self.config = config or default_session_config()
        self.artifact_paths = self.config.artifact_paths
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
                "Missing session retrieval artifact(s): "
                f"{missing_labels}. Run the Phase 3 retrieval scripts first."
            )

        self._index = faiss.read_index(str(self.artifact_paths.index_path))

        with self.artifact_paths.product_id_lookup_path.open("r", encoding="utf-8") as handle:
            self._product_id_lookup = json.load(handle)

        if self._index.ntotal != len(self._product_id_lookup):
            raise ValueError("FAISS index size does not match product_id lookup length.")

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
                "colour_group_name",
                "department_name",
                "image_path",
                "has_image",
            ],
        )
        self._products["product_id"] = self._products["product_id"].astype(str)
        self._products = self._products.set_index("product_id", drop=False)

        if self.artifact_paths.metadata_path.exists():
            with self.artifact_paths.metadata_path.open("r", encoding="utf-8") as handle:
                self._metadata = json.load(handle)

    def _resolve_session_id(self, request: SessionRecommendationsRequest) -> str | None:
        if request.session is not None:
            return request.session.session_id

        for event in [*request.session_events, *request.like_events, *request.save_events]:
            if event.session_id:
                return event.session_id
        return None

    def _collect_recent_signals(
        self,
        request: SessionRecommendationsRequest,
    ) -> tuple[list[SessionSignal], int]:
        signals: list[SessionSignal] = []
        ignored_event_count = 0

        for event in request.session_events:
            if not event.product_id:
                ignored_event_count += 1
                continue

            signal_type = str(event.event_type)
            if signal_type not in self.config.session_event_weights:
                ignored_event_count += 1
                continue

            signals.append(
                SessionSignal(
                    event_id=event.event_id,
                    signal_type=signal_type,
                    product_id=event.product_id,
                    event_timestamp=event.event_timestamp,
                    weight=self.config.session_event_weights[signal_type],
                )
            )

        for event in request.like_events:
            signals.append(
                SessionSignal(
                    event_id=event.event_id,
                    signal_type="like",
                    product_id=event.product_id,
                    event_timestamp=event.event_timestamp,
                    weight=self.config.action_weights["like"],
                )
            )

        for event in request.save_events:
            signals.append(
                SessionSignal(
                    event_id=event.event_id,
                    signal_type="save",
                    product_id=event.product_id,
                    event_timestamp=event.event_timestamp,
                    weight=self.config.action_weights["save"],
                )
            )

        signals.sort(key=lambda signal: signal.event_timestamp, reverse=True)

        max_recent_events = request.max_recent_events or self.config.max_recent_events
        if len(signals) > max_recent_events:
            ignored_event_count += len(signals) - max_recent_events
            signals = signals[:max_recent_events]

        return signals, ignored_event_count

    def _build_session_embedding(
        self,
        recent_signals: list[SessionSignal],
    ) -> tuple[np.ndarray | None, list[SessionSignal], list[str]]:
        assert self._index is not None
        assert self._product_id_to_row is not None

        weighted_sum: np.ndarray | None = None
        total_weight = 0.0
        used_signals: list[SessionSignal] = []
        unknown_product_ids: list[str] = []

        for signal in recent_signals:
            row_index = self._product_id_to_row.get(signal.product_id)
            if row_index is None:
                unknown_product_ids.append(signal.product_id)
                continue

            product_vector = np.asarray(
                self._index.reconstruct(row_index),
                dtype=np.float32,
            )
            if weighted_sum is None:
                weighted_sum = np.zeros_like(product_vector, dtype=np.float32)

            weighted_sum += signal.weight * product_vector
            total_weight += float(signal.weight)
            used_signals.append(signal)

        if weighted_sum is None or total_weight <= 0.0:
            return None, used_signals, unique_in_order(unknown_product_ids)

        session_vector = weighted_sum / total_weight
        session_vector = l2_normalize_vector(session_vector.astype(np.float32))
        return session_vector.reshape(1, -1), used_signals, unique_in_order(unknown_product_ids)

    def _build_signal_summaries(self, used_signals: list[SessionSignal]) -> list[SessionSignalSummary]:
        return [
            SessionSignalSummary(
                event_id=signal.event_id,
                signal_type=signal.signal_type,
                product_id=signal.product_id,
                event_timestamp=signal.event_timestamp,
                weight=signal.weight,
            )
            for signal in used_signals
        ]

    def _empty_response(
        self,
        request: SessionRecommendationsRequest,
        message: str,
        max_recent_events: int,
        ignored_event_count: int,
        unknown_product_ids: list[str] | None = None,
        used_signals: list[SessionSignal] | None = None,
    ) -> SessionRecommendationsResponse:
        used_signals = used_signals or []
        unknown_product_ids = unknown_product_ids or []
        return SessionRecommendationsResponse(
            query_session_id=self._resolve_session_id(request),
            k=request.k,
            retrieval_method="session_multimodal_weighted_average",
            score_source="session_embedding_similarity",
            model_name=self._metadata.get("model_name"),
            fusion_alpha=self._metadata.get("fusion_alpha"),
            max_recent_events=max_recent_events,
            exclude_recent_products=request.exclude_recent_products,
            usable_signal_count=len(used_signals),
            ignored_event_count=ignored_event_count,
            unknown_product_ids=unknown_product_ids,
            used_product_ids=unique_in_order([signal.product_id for signal in used_signals]),
            supported_signal_types=[
                *self.config.session_event_weights.keys(),
                *self.config.action_weights.keys(),
            ],
            message=message,
            used_signals=self._build_signal_summaries(used_signals),
            results=[],
        )

    def get_recommendations(
        self,
        request: SessionRecommendationsRequest,
    ) -> SessionRecommendationsResponse:
        self._load_artifacts()
        assert self._index is not None
        assert self._product_id_lookup is not None
        assert self._products is not None

        max_recent_events = request.max_recent_events or self.config.max_recent_events
        recent_signals, ignored_event_count = self._collect_recent_signals(request)

        if not request.session_events and not request.like_events and not request.save_events:
            return self._empty_response(
                request=request,
                message="Session request contains no recent events. Returning no session-based candidates.",
                max_recent_events=max_recent_events,
                ignored_event_count=ignored_event_count,
            )

        if not recent_signals:
            return self._empty_response(
                request=request,
                message=(
                    "Session request has no supported product-linked events. "
                    "Returning no session-based candidates."
                ),
                max_recent_events=max_recent_events,
                ignored_event_count=ignored_event_count,
            )

        session_vector, used_signals, unknown_product_ids = self._build_session_embedding(
            recent_signals
        )

        if session_vector is None:
            return self._empty_response(
                request=request,
                message=(
                    "No usable recent session products matched the multimodal index. "
                    "Returning no session-based candidates."
                ),
                max_recent_events=max_recent_events,
                ignored_event_count=ignored_event_count,
                unknown_product_ids=unknown_product_ids,
                used_signals=used_signals,
            )

        seen_product_ids = unique_in_order([signal.product_id for signal in recent_signals])
        search_k = min(
            max(request.k + len(seen_product_ids) + 10, request.k),
            len(self._product_id_lookup),
        )

        scores, row_indices = self._index.search(session_vector, search_k)

        results: list[SessionRecommendation] = []
        for score, row_index in zip(scores[0], row_indices[0]):
            if row_index < 0:
                continue

            candidate_product_id = self._product_id_lookup[row_index]
            if request.exclude_recent_products and candidate_product_id in seen_product_ids:
                continue
            if candidate_product_id not in self._products.index:
                continue

            product = self._products.loc[candidate_product_id]
            results.append(
                SessionRecommendation(
                    product_id=candidate_product_id,
                    product_name=str(product["product_name"]),
                    product_type_name=product["product_type_name"],
                    product_group_name=product["product_group_name"],
                    colour_group_name=product["colour_group_name"],
                    department_name=product["department_name"],
                    image_path=product["image_path"],
                    has_image=bool(product["has_image"]),
                    score=float(score),
                )
            )

            if len(results) >= request.k:
                break

        message = None
        if not results:
            if request.exclude_recent_products:
                message = (
                    "Usable session context was found, but no unseen candidates remained "
                    "after excluding recent session products."
                )
            else:
                message = (
                    "Usable session context was found, but no products were returned from "
                    "the multimodal index."
                )

        return SessionRecommendationsResponse(
            query_session_id=self._resolve_session_id(request),
            k=request.k,
            retrieval_method="session_multimodal_weighted_average",
            score_source="session_embedding_similarity",
            model_name=self._metadata.get("model_name"),
            fusion_alpha=self._metadata.get("fusion_alpha"),
            max_recent_events=max_recent_events,
            exclude_recent_products=request.exclude_recent_products,
            usable_signal_count=len(used_signals),
            ignored_event_count=ignored_event_count,
            unknown_product_ids=unknown_product_ids,
            used_product_ids=unique_in_order([signal.product_id for signal in used_signals]),
            supported_signal_types=[
                *self.config.session_event_weights.keys(),
                *self.config.action_weights.keys(),
            ],
            message=message,
            used_signals=self._build_signal_summaries(used_signals),
            results=results,
        )


@lru_cache(maxsize=1)
def get_session_retrieval_service() -> SessionRetrievalService:
    return SessionRetrievalService()
