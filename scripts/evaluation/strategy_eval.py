from dataclasses import dataclass

try:
    from .config import OfflineEvaluationConfig
    from .helpers import (
        RecommendationOfflineAdapter,
        UserEvaluationProfile,
        load_strategy_definitions,
    )
    from .metrics import MetricAccumulator
except ImportError:
    from config import OfflineEvaluationConfig
    from helpers import RecommendationOfflineAdapter, UserEvaluationProfile, load_strategy_definitions
    from metrics import MetricAccumulator

SOURCE_COLLABORATIVE = "collaborative"
SOURCE_CONTENT = "content"


@dataclass
class SharedCandidateStats:
    evaluated_user_count: int = 0
    users_with_content_source: int = 0
    users_with_collaborative_popularity_fallback: int = 0
    users_with_no_candidates_before_seen_filter: int = 0
    users_with_no_candidates_after_seen_filter: int = 0
    total_candidates_before_seen_filter: int = 0
    total_candidates_after_seen_filter: int = 0
    total_seen_candidates_removed: int = 0

    def update(self, blended_response, filtered_response) -> None:
        self.evaluated_user_count += 1
        self.total_candidates_before_seen_filter += len(blended_response.results)
        self.total_candidates_after_seen_filter += len(filtered_response.results)
        self.total_seen_candidates_removed += max(
            len(blended_response.results) - len(filtered_response.results),
            0,
        )

        if not blended_response.results:
            self.users_with_no_candidates_before_seen_filter += 1
        if not filtered_response.results:
            self.users_with_no_candidates_after_seen_filter += 1

        for source_summary in blended_response.source_summaries:
            if source_summary.source == SOURCE_CONTENT and source_summary.used:
                self.users_with_content_source += 1
            if (
                source_summary.source == SOURCE_COLLABORATIVE
                and source_summary.score_label == "global_popularity"
            ):
                self.users_with_collaborative_popularity_fallback += 1

    def to_summary_dict(self) -> dict[str, object]:
        user_count = max(self.evaluated_user_count, 1)
        return {
            "evaluated_user_count": self.evaluated_user_count,
            "content_source_used_rate": self.users_with_content_source / float(user_count),
            "collaborative_popularity_fallback_rate": (
                self.users_with_collaborative_popularity_fallback / float(user_count)
            ),
            "no_candidates_before_seen_filter_rate": (
                self.users_with_no_candidates_before_seen_filter / float(user_count)
            ),
            "no_candidates_after_seen_filter_rate": (
                self.users_with_no_candidates_after_seen_filter / float(user_count)
            ),
            "avg_candidates_before_seen_filter": (
                self.total_candidates_before_seen_filter / float(user_count)
            ),
            "avg_candidates_after_seen_filter": (
                self.total_candidates_after_seen_filter / float(user_count)
            ),
            "avg_seen_candidates_removed": self.total_seen_candidates_removed / float(user_count),
        }


def evaluate_strategies(
    config: OfflineEvaluationConfig,
    user_profiles: list[UserEvaluationProfile],
    catalog_size: int,
    popularity_by_product: dict[str, int],
) -> dict[str, object]:
    if not user_profiles:
        raise ValueError("No user profiles were provided for offline evaluation.")

    adapter = RecommendationOfflineAdapter(config)
    strategy_definitions = load_strategy_definitions(config.strategy_keys)
    metric_accumulators = {
        strategy_definition.key: {
            metric_k: MetricAccumulator(
                k=metric_k,
                catalog_size=catalog_size,
                popularity_by_product=popularity_by_product,
            )
            for metric_k in config.metric_ks
        }
        for strategy_definition in strategy_definitions
    }
    shared_candidate_stats = SharedCandidateStats()

    for user_index, profile in enumerate(user_profiles, start=1):
        blended_response = adapter.blend_candidates_for_user(profile)
        filtered_response = adapter.filter_seen_candidates(
            blended_response=blended_response,
            train_product_ids=profile.train_product_ids,
        )
        shared_candidate_stats.update(
            blended_response=blended_response,
            filtered_response=filtered_response,
        )

        for strategy_definition in strategy_definitions:
            reranked_response = adapter.rerank_candidates(
                profile=profile,
                strategy_key=strategy_definition.key,
                blended_response=filtered_response,
            )
            for metric_k in config.metric_ks:
                metric_accumulators[strategy_definition.key][metric_k].update(
                    recommendations=reranked_response.results,
                    relevant_product_ids=profile.relevant_product_ids,
                )

        if config.log_every_users and user_index % config.log_every_users == 0:
            print(
                f"Evaluated {user_index:,} / {len(user_profiles):,} users...",
                flush=True,
            )

    strategy_results: list[dict[str, object]] = []
    metrics_rows: list[dict[str, object]] = []

    for strategy_definition in strategy_definitions:
        metrics_by_k: list[dict[str, object]] = []
        for metric_k in config.metric_ks:
            metric_row = metric_accumulators[strategy_definition.key][metric_k].finalize()
            metric_row["strategy_key"] = strategy_definition.key
            metric_row["strategy_name"] = strategy_definition.name
            metric_row["strategy_description"] = strategy_definition.description
            metrics_by_k.append(metric_row)
            metrics_rows.append(metric_row)

        strategy_results.append(
            {
                "strategy": strategy_definition.model_dump(),
                "metrics_by_k": metrics_by_k,
            }
        )

    comparison_rows = build_strategy_comparison_rows(
        strategy_results=strategy_results,
        report_k=config.report_k,
    )

    return {
        "shared_candidate_stats": shared_candidate_stats.to_summary_dict(),
        "strategy_results": strategy_results,
        "metrics_rows": metrics_rows,
        "comparison_rows": comparison_rows,
    }


def build_strategy_comparison_rows(
    strategy_results: list[dict[str, object]],
    report_k: int,
) -> list[dict[str, object]]:
    comparison_rows: list[dict[str, object]] = []

    for strategy_result in strategy_results:
        strategy_definition = strategy_result["strategy"]
        report_row = next(
            metric_row
            for metric_row in strategy_result["metrics_by_k"]
            if metric_row["k"] == report_k
        )
        feature_weights = strategy_definition["config"]["feature_weights"]
        diversity_config = strategy_definition["config"]["diversity"]

        comparison_rows.append(
            {
                "strategy_key": strategy_definition["key"],
                "strategy_name": strategy_definition["name"],
                "strategy_description": strategy_definition["description"],
                "report_k": report_k,
                "precision_at_report_k": report_row["precision_at_k"],
                "recall_at_report_k": report_row["recall_at_k"],
                "ndcg_at_report_k": report_row["ndcg_at_k"],
                "catalog_coverage_at_report_k": report_row["catalog_coverage_at_k"],
                "avg_recommendation_popularity_at_report_k": (
                    report_row["avg_recommendation_popularity_at_k"]
                ),
                "avg_repeated_product_type_ratio_at_report_k": (
                    report_row["avg_repeated_product_type_ratio_at_k"]
                ),
                "avg_repeated_product_group_ratio_at_report_k": (
                    report_row["avg_repeated_product_group_ratio_at_k"]
                ),
                "avg_returned_count_at_report_k": report_row["avg_returned_count_at_k"],
                "feature_weight_blended_score": feature_weights["blended_score"],
                "feature_weight_search_signal": feature_weights["search_signal"],
                "feature_weight_search_presence": feature_weights["search_presence"],
                "feature_weight_session_signal": feature_weights["session_signal"],
                "feature_weight_session_presence": feature_weights["session_presence"],
                "feature_weight_content_signal": feature_weights["content_signal"],
                "feature_weight_collaborative_signal": feature_weights["collaborative_signal"],
                "feature_weight_popularity_signal": feature_weights["popularity_signal"],
                "feature_weight_multi_source_signal": feature_weights["multi_source_signal"],
                "feature_weight_exact_anchor_penalty": feature_weights["exact_anchor_penalty"],
                "diversity_enabled": diversity_config["enabled"],
                "diversity_apply_top_n": diversity_config["apply_top_n"],
                "diversity_product_type_penalty": diversity_config["product_type_penalty"],
                "diversity_product_group_penalty": diversity_config["product_group_penalty"],
                "diversity_max_penalty": diversity_config["max_penalty"],
            }
        )

    comparison_rows.sort(
        key=lambda row: (
            -row["ndcg_at_report_k"],
            -row["recall_at_report_k"],
            row["strategy_key"],
        )
    )
    return comparison_rows
