from dataclasses import dataclass
from pathlib import Path

DEFAULT_STRATEGY_KEYS = (
    "default",
    "search_intent_boosted",
    "session_boosted",
    "diversity_boosted",
)

DEFAULT_METRIC_KS = (10, 20, 50)
DEFAULT_REPORT_K = 20
DEFAULT_SAMPLE_SEED = 2026
DEFAULT_PARQUET_BATCH_SIZE = 250_000
DEFAULT_COLLABORATIVE_K = 100
DEFAULT_CONTENT_K = 60
DEFAULT_BLENDED_K = 100
DEFAULT_LOG_EVERY_USERS = 250


def parse_metric_ks(raw_value: str) -> tuple[int, ...]:
    metric_ks: list[int] = []
    for part in raw_value.split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        parsed_value = int(cleaned)
        if parsed_value <= 0:
            raise ValueError("Metric cutoffs must be positive integers.")
        metric_ks.append(parsed_value)

    unique_metric_ks = tuple(sorted(set(metric_ks)))
    if not unique_metric_ks:
        raise ValueError("Provide at least one metric cutoff in --metric-ks.")
    return unique_metric_ks


@dataclass(frozen=True)
class OfflineEvaluationPaths:
    repo_root: Path
    train_interactions_path: Path
    val_interactions_path: Path
    products_path: Path
    split_metadata_path: Path
    reports_dir: Path


def default_paths() -> OfflineEvaluationPaths:
    repo_root = Path(__file__).resolve().parents[2]
    return OfflineEvaluationPaths(
        repo_root=repo_root,
        train_interactions_path=repo_root / "data" / "processed" / "interactions_train.parquet",
        val_interactions_path=repo_root / "data" / "processed" / "interactions_val.parquet",
        products_path=repo_root / "data" / "processed" / "products.parquet",
        split_metadata_path=repo_root / "data" / "processed" / "split_metadata.json",
        reports_dir=repo_root / "artifacts" / "reports",
    )


@dataclass(frozen=True)
class OfflineEvaluationConfig:
    paths: OfflineEvaluationPaths
    strategy_keys: tuple[str, ...] = DEFAULT_STRATEGY_KEYS
    metric_ks: tuple[int, ...] = DEFAULT_METRIC_KS
    report_k: int = DEFAULT_REPORT_K
    max_users: int | None = None
    sample_seed: int = DEFAULT_SAMPLE_SEED
    parquet_batch_size: int = DEFAULT_PARQUET_BATCH_SIZE
    collaborative_k: int = DEFAULT_COLLABORATIVE_K
    content_k: int = DEFAULT_CONTENT_K
    blended_k: int = DEFAULT_BLENDED_K
    use_latest_train_anchor: bool = True
    apply_seen_filter_before_reranking: bool = True
    log_every_users: int = DEFAULT_LOG_EVERY_USERS

    @property
    def reranked_k(self) -> int:
        return max(self.metric_ks)

    def validate(self) -> None:
        if self.report_k not in self.metric_ks:
            raise ValueError("report_k must be one of the configured metric cutoffs.")
        if self.blended_k < self.reranked_k:
            raise ValueError("blended_k must be at least as large as the largest metric cutoff.")
        if self.collaborative_k <= 0:
            raise ValueError("collaborative_k must be positive.")
        if self.content_k <= 0:
            raise ValueError("content_k must be positive.")
        if self.parquet_batch_size <= 0:
            raise ValueError("parquet_batch_size must be positive.")
        if self.max_users is not None and self.max_users <= 0:
            raise ValueError("max_users must be positive when provided.")
        if self.log_every_users < 0:
            raise ValueError("log_every_users cannot be negative.")

    def to_summary_dict(self) -> dict[str, object]:
        return {
            "strategy_keys": list(self.strategy_keys),
            "metric_ks": list(self.metric_ks),
            "report_k": self.report_k,
            "max_users": self.max_users,
            "sample_seed": self.sample_seed,
            "parquet_batch_size": self.parquet_batch_size,
            "collaborative_k": self.collaborative_k,
            "content_k": self.content_k,
            "blended_k": self.blended_k,
            "reranked_k": self.reranked_k,
            "use_latest_train_anchor": self.use_latest_train_anchor,
            "apply_seen_filter_before_reranking": self.apply_seen_filter_before_reranking,
            "log_every_users": self.log_every_users,
            "paths": {
                "train_interactions_path": self.paths.train_interactions_path.as_posix(),
                "val_interactions_path": self.paths.val_interactions_path.as_posix(),
                "products_path": self.paths.products_path.as_posix(),
                "split_metadata_path": self.paths.split_metadata_path.as_posix(),
                "reports_dir": self.paths.reports_dir.as_posix(),
            },
        }
