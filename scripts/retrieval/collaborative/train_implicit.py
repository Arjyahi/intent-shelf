import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, save_npz

try:
    from implicit.cpu.bpr import BayesianPersonalizedRanking
except ImportError as exc:
    BayesianPersonalizedRanking = Any  # type: ignore[assignment]
    IMPLICIT_IMPORT_ERROR = exc
else:
    IMPLICIT_IMPORT_ERROR = None

try:
    from .config import (
        CollaborativeArtifactPaths,
        CollaborativeTrainingConfig,
        default_artifact_paths,
        default_training_config,
    )
    from .matrix_builder import build_collaborative_matrix_artifacts
except ImportError:
    from config import (
        CollaborativeArtifactPaths,
        CollaborativeTrainingConfig,
        default_artifact_paths,
        default_training_config,
    )
    from matrix_builder import build_collaborative_matrix_artifacts


def require_implicit() -> None:
    if IMPLICIT_IMPORT_ERROR is not None:
        raise ImportError(
            "implicit is required for Phase 4 collaborative retrieval. "
            "Install backend/requirements.txt before training this model."
        ) from IMPLICIT_IMPORT_ERROR


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_directories(paths: list[Path]) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def save_lookup(path: Path, values: list[str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(values, handle)


def build_bpr_training_matrix(interaction_matrix: csr_matrix) -> csr_matrix:
    """
    Convert weighted purchase counts into binary positives for BPR training.

    The aggregated weighted matrix is still saved as an artifact because it is
    useful for popularity fallback logic and later phases.
    """

    training_matrix = interaction_matrix.copy().tocsr().astype(np.float32)
    training_matrix.data = np.ones(training_matrix.nnz, dtype=np.float32)
    return training_matrix


def train_implicit_model(
    interaction_matrix: csr_matrix,
    config: CollaborativeTrainingConfig,
) -> BayesianPersonalizedRanking:
    require_implicit()

    if config.model_backend != "implicit":
        raise ValueError(f"Unsupported collaborative backend: {config.model_backend}")
    if config.model_type != "bpr":
        raise ValueError(
            "This Phase 4 patch currently supports only implicit BPR. "
            f"Received model_type={config.model_type!r}."
        )

    training_matrix = build_bpr_training_matrix(interaction_matrix)
    model = BayesianPersonalizedRanking(
        factors=config.factors,
        learning_rate=config.learning_rate,
        regularization=config.regularization,
        iterations=config.iterations,
        verify_negative_samples=config.verify_negative_samples,
        num_threads=config.num_threads,
        random_state=config.random_seed,
    )
    model.fit(training_matrix, show_progress=False)
    return model


def build_training_metadata(
    config: CollaborativeTrainingConfig,
    artifact_paths: CollaborativeArtifactPaths,
    matrix_artifacts,
    limit_rows: int | None,
) -> dict[str, object]:
    summary = matrix_artifacts.summary
    return {
        "generated_at": utc_timestamp(),
        "phase": "phase_4_collaborative_retrieval",
        "model_backend": config.model_backend,
        "model_name": "implicit",
        "model_type": config.model_type,
        "library_model_class": "BayesianPersonalizedRanking",
        "loss": config.model_type,
        "factors": config.factors,
        "iterations": config.iterations,
        "learning_rate": config.learning_rate,
        "regularization": config.regularization,
        "verify_negative_samples": config.verify_negative_samples,
        "num_threads": config.num_threads,
        "random_seed": config.random_seed,
        "top_k_default": config.top_k_default,
        "exclude_seen_items_default": config.exclude_seen_items_default,
        "unknown_user_fallback": "global_popularity",
        "min_user_interactions": config.min_user_interactions,
        "min_product_interactions": config.min_product_interactions,
        "interaction_batch_size": config.interaction_batch_size,
        "limit_rows": limit_rows,
        "input_interactions_path": config.interactions_path.as_posix(),
        "input_products_path": config.products_path.as_posix(),
        "output_model_path": artifact_paths.model_path.as_posix(),
        "output_user_lookup_path": artifact_paths.user_id_lookup_path.as_posix(),
        "output_product_lookup_path": artifact_paths.product_id_lookup_path.as_posix(),
        "output_user_item_matrix_path": artifact_paths.user_item_matrix_path.as_posix(),
        "output_training_metadata_path": artifact_paths.training_metadata_path.as_posix(),
        "raw_rows_loaded": summary.raw_rows,
        "rows_after_catalog_filter": summary.rows_after_catalog_filter,
        "aggregated_user_product_rows": summary.aggregated_rows,
        "duplicate_rows_collapsed": summary.duplicate_rows_collapsed,
        "dropped_missing_product_rows": summary.dropped_missing_product_rows,
        "unique_users_before_thresholds": summary.unique_users_before_thresholds,
        "unique_products_before_thresholds": summary.unique_products_before_thresholds,
        "unique_users_after_thresholds": summary.unique_users_after_thresholds,
        "unique_products_after_thresholds": summary.unique_products_after_thresholds,
        "matrix_shape": [summary.matrix_rows, summary.matrix_cols],
        "matrix_nnz": summary.matrix_nnz,
        "notes": [
            "Training uses data/processed/interactions_train.parquet only.",
            "Duplicate user-product rows are summed into one interaction_strength value.",
            "The saved matrix keeps weighted interaction strengths, but implicit BPR trains on binary positive interactions from the non-zero entries.",
            "Unknown users fall back to global popularity derived from the saved interaction matrix.",
            "TODO(phase-5): blend collaborative candidates with content, search, and session candidates.",
        ],
    }


def train_and_save_artifacts(
    config: CollaborativeTrainingConfig | None = None,
    artifact_paths: CollaborativeArtifactPaths | None = None,
    limit_rows: int | None = None,
) -> dict[str, object]:
    config = config or default_training_config()
    artifact_paths = artifact_paths or config.artifact_paths

    if not config.interactions_path.exists():
        raise FileNotFoundError(
            "Missing interactions_train.parquet. Run the Phase 1 preprocessing and time split first."
        )
    if not config.products_path.exists():
        raise FileNotFoundError(
            "Missing products.parquet. Run the Phase 1 preprocessing pipeline first."
        )
    if config.min_user_interactions <= 0:
        raise ValueError("min_user_interactions must be a positive integer.")
    if config.min_product_interactions <= 0:
        raise ValueError("min_product_interactions must be a positive integer.")

    matrix_artifacts = build_collaborative_matrix_artifacts(
        interactions_path=config.interactions_path,
        products_path=config.products_path,
        limit_rows=limit_rows,
        batch_size=config.interaction_batch_size,
        min_user_interactions=config.min_user_interactions,
        min_product_interactions=config.min_product_interactions,
    )

    if matrix_artifacts.interaction_matrix.nnz == 0:
        raise ValueError(
            "The collaborative interaction matrix is empty after filtering. "
            "Lower the thresholds or inspect the training inputs."
        )

    model = train_implicit_model(
        interaction_matrix=matrix_artifacts.interaction_matrix,
        config=config,
    )

    ensure_parent_directories(
        [
            artifact_paths.model_path,
            artifact_paths.user_id_lookup_path,
            artifact_paths.product_id_lookup_path,
            artifact_paths.user_item_matrix_path,
            artifact_paths.training_metadata_path,
        ]
    )

    model.save(str(artifact_paths.model_path))

    save_lookup(artifact_paths.user_id_lookup_path, matrix_artifacts.user_id_lookup)
    save_lookup(artifact_paths.product_id_lookup_path, matrix_artifacts.product_id_lookup)
    save_npz(artifact_paths.user_item_matrix_path, matrix_artifacts.interaction_matrix)

    metadata = build_training_metadata(
        config=config,
        artifact_paths=artifact_paths,
        matrix_artifacts=matrix_artifacts,
        limit_rows=limit_rows,
    )
    save_json(artifact_paths.training_metadata_path, metadata)
    return metadata


def parse_args() -> argparse.Namespace:
    defaults = default_training_config()

    parser = argparse.ArgumentParser(
        description="Train an implicit BPR collaborative retrieval model from interactions_train.parquet."
    )
    parser.add_argument(
        "--interactions-path",
        type=Path,
        default=defaults.interactions_path,
        help="Path to the training interactions parquet file.",
    )
    parser.add_argument(
        "--products-path",
        type=Path,
        default=defaults.products_path,
        help="Path to the processed products parquet file.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=defaults.artifact_paths.model_path,
        help="Where to save the trained implicit model artifact.",
    )
    parser.add_argument(
        "--user-lookup-path",
        type=Path,
        default=defaults.artifact_paths.user_id_lookup_path,
        help="Where to save the user_id lookup list.",
    )
    parser.add_argument(
        "--product-lookup-path",
        type=Path,
        default=defaults.artifact_paths.product_id_lookup_path,
        help="Where to save the product_id lookup list.",
    )
    parser.add_argument(
        "--user-item-matrix-path",
        type=Path,
        default=defaults.artifact_paths.user_item_matrix_path,
        help="Where to save the sparse user-item matrix used at inference time.",
    )
    parser.add_argument(
        "--training-metadata-path",
        type=Path,
        default=defaults.artifact_paths.training_metadata_path,
        help="Where to save the training metadata JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit for fast local iteration.",
    )
    parser.add_argument(
        "--min-user-interactions",
        type=int,
        default=defaults.min_user_interactions,
        help="Keep users with at least this many unique interacted products after duplicate aggregation.",
    )
    parser.add_argument(
        "--min-product-interactions",
        type=int,
        default=defaults.min_product_interactions,
        help="Keep products with at least this many unique interacting users after duplicate aggregation.",
    )
    parser.add_argument(
        "--model-type",
        type=str,
        default=defaults.model_type,
        help="Collaborative model type. Default is bpr.",
    )
    parser.add_argument(
        "--factors",
        type=int,
        default=defaults.factors,
        help="Number of latent factors in the implicit BPR model.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=defaults.iterations,
        help="Number of BPR training iterations.",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=defaults.learning_rate,
        help="BPR learning rate.",
    )
    parser.add_argument(
        "--regularization",
        type=float,
        default=defaults.regularization,
        help="BPR regularization strength.",
    )
    parser.add_argument(
        "--verify-negative-samples",
        action=argparse.BooleanOptionalAction,
        default=defaults.verify_negative_samples,
        help="Whether BPR should resample negatives that are actually liked items.",
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=defaults.num_threads,
        help="Number of CPU threads used during implicit training.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=defaults.random_seed,
        help="Random seed for repeatable training runs.",
    )
    parser.add_argument(
        "--interaction-batch-size",
        type=int,
        default=defaults.interaction_batch_size,
        help="Parquet batch size used only when --limit is provided.",
    )
    parser.add_argument(
        "--top-k-default",
        type=int,
        default=defaults.top_k_default,
        help="Default recommendation count stored in the training metadata.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    artifact_paths = CollaborativeArtifactPaths(
        model_path=args.model_path,
        user_id_lookup_path=args.user_lookup_path,
        product_id_lookup_path=args.product_lookup_path,
        user_item_matrix_path=args.user_item_matrix_path,
        training_metadata_path=args.training_metadata_path,
    )
    config = CollaborativeTrainingConfig(
        interactions_path=args.interactions_path,
        products_path=args.products_path,
        top_k_default=args.top_k_default,
        exclude_seen_items_default=True,
        random_seed=args.random_seed,
        interaction_batch_size=args.interaction_batch_size,
        min_user_interactions=args.min_user_interactions,
        min_product_interactions=args.min_product_interactions,
        model_type=args.model_type,
        factors=args.factors,
        iterations=args.iterations,
        learning_rate=args.learning_rate,
        regularization=args.regularization,
        verify_negative_samples=args.verify_negative_samples,
        num_threads=args.num_threads,
        artifact_paths=artifact_paths,
    )

    metadata = train_and_save_artifacts(
        config=config,
        artifact_paths=artifact_paths,
        limit_rows=args.limit,
    )

    print("Collaborative implicit BPR training complete.")
    print(f"  model_path: {artifact_paths.model_path.as_posix()}")
    print(f"  user_lookup_path: {artifact_paths.user_id_lookup_path.as_posix()}")
    print(f"  product_lookup_path: {artifact_paths.product_id_lookup_path.as_posix()}")
    print(f"  user_item_matrix_path: {artifact_paths.user_item_matrix_path.as_posix()}")
    print(f"  training_metadata_path: {artifact_paths.training_metadata_path.as_posix()}")
    print(f"  matrix_shape: {metadata['matrix_shape']}")
    print(f"  matrix_nnz: {metadata['matrix_nnz']:,}")
    print(f"  duplicate_rows_collapsed: {metadata['duplicate_rows_collapsed']:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
