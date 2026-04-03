import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    from .config import OfflineEvaluationConfig
except ImportError:
    from config import OfflineEvaluationConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.retrieval import BlendedCandidatesRequest, BlendedCandidatesResponse, FeedRerankRequest
from app.services.candidate_blending import get_candidate_blending_service
from app.services.ranking_strategies import get_ranking_strategy_registry
from app.services.reranking import get_feed_reranking_service


@dataclass(frozen=True)
class ValidationUserTarget:
    user_id: str
    relevant_product_ids: list[str]
    val_interaction_count: int


@dataclass
class UserTrainHistory:
    interaction_count: int = 0
    unique_product_ids: set[str] = field(default_factory=set)
    latest_sort_key: tuple[pd.Timestamp, str] | None = None
    latest_train_product_id: str | None = None


@dataclass(frozen=True)
class UserEvaluationProfile:
    user_id: str
    train_product_ids: set[str]
    anchor_product_id: str | None
    relevant_product_ids: set[str]
    val_product_ids: list[str]
    train_interaction_count: int
    val_interaction_count: int


@dataclass(frozen=True)
class TrainScanArtifacts:
    histories_by_user: dict[str, UserTrainHistory]
    product_popularity_by_id: dict[str, int]
    total_train_rows: int


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_markdown(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def load_validation_targets(
    val_interactions_path: Path,
) -> dict[str, ValidationUserTarget]:
    validation_frame = pd.read_parquet(
        val_interactions_path,
        columns=["user_id", "product_id"],
    )
    validation_frame["user_id"] = validation_frame["user_id"].astype(str)
    validation_frame["product_id"] = validation_frame["product_id"].astype(str)

    validation_targets: dict[str, ValidationUserTarget] = {}
    for user_id, user_rows in validation_frame.groupby("user_id", sort=True):
        relevant_product_ids = sorted(set(user_rows["product_id"].tolist()))
        validation_targets[user_id] = ValidationUserTarget(
            user_id=user_id,
            relevant_product_ids=relevant_product_ids,
            val_interaction_count=int(len(user_rows)),
        )

    return validation_targets


def select_candidate_user_ids(
    validation_targets: dict[str, ValidationUserTarget],
    max_users: int | None,
    sample_seed: int,
) -> list[str]:
    sorted_user_ids = sorted(validation_targets)
    if max_users is None or max_users >= len(sorted_user_ids):
        return sorted_user_ids

    random_generator = np.random.default_rng(sample_seed)
    sampled_user_ids = random_generator.choice(
        np.asarray(sorted_user_ids),
        size=max_users,
        replace=False,
    )
    return sorted(str(user_id) for user_id in sampled_user_ids.tolist())


def scan_train_histories(
    train_interactions_path: Path,
    target_user_ids: list[str],
    batch_size: int,
) -> TrainScanArtifacts:
    parquet_file = pq.ParquetFile(train_interactions_path)
    target_user_lookup = set(target_user_ids)
    histories_by_user = {
        user_id: UserTrainHistory()
        for user_id in target_user_lookup
    }
    product_popularity = Counter()
    total_train_rows = 0

    for batch in parquet_file.iter_batches(
        columns=["user_id", "product_id", "t_dat"],
        batch_size=batch_size,
    ):
        batch_frame = batch.to_pandas()
        batch_frame["user_id"] = batch_frame["user_id"].astype(str)
        batch_frame["product_id"] = batch_frame["product_id"].astype(str)
        total_train_rows += int(len(batch_frame))
        product_popularity.update(batch_frame["product_id"].value_counts().to_dict())

        if not target_user_lookup:
            continue

        user_rows = batch_frame[batch_frame["user_id"].isin(target_user_lookup)]
        if user_rows.empty:
            continue

        user_rows = user_rows.copy()
        user_rows["t_dat"] = pd.to_datetime(user_rows["t_dat"])

        for user_id, grouped_rows in user_rows.groupby("user_id", sort=False):
            history = histories_by_user[user_id]
            history.interaction_count += int(len(grouped_rows))
            history.unique_product_ids.update(grouped_rows["product_id"].tolist())

            latest_row = grouped_rows.sort_values(["t_dat", "product_id"]).iloc[-1]
            latest_sort_key = (
                pd.Timestamp(latest_row["t_dat"]),
                str(latest_row["product_id"]),
            )
            if history.latest_sort_key is None or latest_sort_key > history.latest_sort_key:
                history.latest_sort_key = latest_sort_key
                history.latest_train_product_id = str(latest_row["product_id"])

    return TrainScanArtifacts(
        histories_by_user=histories_by_user,
        product_popularity_by_id=dict(product_popularity),
        total_train_rows=total_train_rows,
    )


def build_user_profiles(
    validation_targets: dict[str, ValidationUserTarget],
    train_scan_artifacts: TrainScanArtifacts,
) -> tuple[list[UserEvaluationProfile], dict[str, int]]:
    profiles: list[UserEvaluationProfile] = []
    dropped_missing_train_history_count = 0

    for user_id in sorted(validation_targets):
        validation_target = validation_targets[user_id]
        train_history = train_scan_artifacts.histories_by_user.get(user_id)
        if train_history is None or train_history.interaction_count == 0:
            dropped_missing_train_history_count += 1
            continue

        profiles.append(
            UserEvaluationProfile(
                user_id=user_id,
                train_product_ids=set(train_history.unique_product_ids),
                anchor_product_id=train_history.latest_train_product_id,
                relevant_product_ids=set(validation_target.relevant_product_ids),
                val_product_ids=list(validation_target.relevant_product_ids),
                train_interaction_count=train_history.interaction_count,
                val_interaction_count=validation_target.val_interaction_count,
            )
        )

    selection_summary = {
        "candidate_validation_user_count": len(validation_targets),
        "evaluated_user_count": len(profiles),
        "dropped_missing_train_history_count": dropped_missing_train_history_count,
    }
    return profiles, selection_summary


def load_catalog_size(products_path: Path) -> int:
    return int(pq.ParquetFile(products_path).metadata.num_rows)


def load_strategy_definitions(strategy_keys: tuple[str, ...]) -> list[object]:
    registry = get_ranking_strategy_registry()
    definitions: list[object] = []
    for strategy_key in strategy_keys:
        strategy_definition = registry.get_strategy(strategy_key)
        if strategy_definition is None:
            raise ValueError(f"Unknown strategy key in evaluation config: {strategy_key}")
        definitions.append(strategy_definition)
    return definitions


class RecommendationOfflineAdapter:
    """
    Thin evaluation adapter that reuses the live blending and reranking logic.

    Offline evaluation only supplies:
    - `user_id`
    - an optional `anchor_product_id` from the user's most recent train purchase

    It intentionally does not fabricate query text or session events.
    """

    def __init__(self, config: OfflineEvaluationConfig) -> None:
        self.config = config
        self.candidate_blending_service = get_candidate_blending_service()
        self.reranking_service = get_feed_reranking_service()

    def build_blend_request(
        self,
        profile: UserEvaluationProfile,
    ) -> BlendedCandidatesRequest:
        anchor_product_id = profile.anchor_product_id if self.config.use_latest_train_anchor else None
        return BlendedCandidatesRequest(
            user_id=profile.user_id,
            anchor_product_id=anchor_product_id,
            collaborative_k=self.config.collaborative_k,
            content_k=self.config.content_k,
            blended_k=self.config.blended_k,
            exclude_seen_items=True,
        )

    def build_rerank_request(
        self,
        profile: UserEvaluationProfile,
        strategy_key: str,
    ) -> FeedRerankRequest:
        anchor_product_id = profile.anchor_product_id if self.config.use_latest_train_anchor else None
        return FeedRerankRequest(
            user_id=profile.user_id,
            anchor_product_id=anchor_product_id,
            collaborative_k=self.config.collaborative_k,
            content_k=self.config.content_k,
            blended_k=self.config.blended_k,
            reranked_k=self.config.reranked_k,
            exclude_seen_items=True,
            ranking_strategy=strategy_key,
        )

    def blend_candidates_for_user(
        self,
        profile: UserEvaluationProfile,
    ) -> BlendedCandidatesResponse:
        blend_request = self.build_blend_request(profile)
        return self.candidate_blending_service.blend_candidates(blend_request)

    def filter_seen_candidates(
        self,
        blended_response: BlendedCandidatesResponse,
        train_product_ids: set[str],
    ) -> BlendedCandidatesResponse:
        if not self.config.apply_seen_filter_before_reranking:
            return blended_response

        filtered_candidates = [
            candidate
            for candidate in blended_response.results
            if candidate.product_id not in train_product_ids
        ]
        message = blended_response.message
        if not filtered_candidates and blended_response.results:
            message = (
                "All blended candidates were removed by the offline seen-item filter "
                "before reranking."
            )

        return blended_response.model_copy(
            update={
                "returned_candidate_count": len(filtered_candidates),
                "message": message,
                "results": filtered_candidates,
            }
        )

    def rerank_candidates(
        self,
        profile: UserEvaluationProfile,
        strategy_key: str,
        blended_response: BlendedCandidatesResponse,
    ):
        rerank_request = self.build_rerank_request(profile, strategy_key)
        return self.reranking_service.rerank_preblended_candidates(
            request=rerank_request,
            blended_response=blended_response,
        )
