import argparse
from pathlib import Path

import pandas as pd

try:
    from .config import OfflineEvaluationConfig, OfflineEvaluationPaths, default_paths, parse_metric_ks
    from .helpers import (
        build_user_profiles,
        ensure_directory,
        load_catalog_size,
        load_json,
        load_validation_targets,
        scan_train_histories,
        select_candidate_user_ids,
        utc_timestamp,
        write_json,
        write_markdown,
    )
    from .strategy_eval import evaluate_strategies
except ImportError:
    from config import OfflineEvaluationConfig, OfflineEvaluationPaths, default_paths, parse_metric_ks
    from helpers import (
        build_user_profiles,
        ensure_directory,
        load_catalog_size,
        load_json,
        load_validation_targets,
        scan_train_histories,
        select_candidate_user_ids,
        utc_timestamp,
        write_json,
        write_markdown,
    )
    from strategy_eval import evaluate_strategies


def parse_args() -> argparse.Namespace:
    default_eval_paths = default_paths()

    parser = argparse.ArgumentParser(
        description=(
            "Run the IntentShelf Phase 12 offline evaluation pipeline on "
            "interactions_train.parquet and interactions_val.parquet."
        )
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=None,
        help="Optional cap for a deterministic sampled evaluation subset.",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=2026,
        help="Random seed used when --max-users is provided.",
    )
    parser.add_argument(
        "--metric-ks",
        type=str,
        default="10,20,50",
        help="Comma-separated metric cutoffs, for example 10,20,50.",
    )
    parser.add_argument(
        "--report-k",
        type=int,
        default=20,
        help="Primary cutoff used in strategy_comparison.csv.",
    )
    parser.add_argument(
        "--collaborative-k",
        type=int,
        default=100,
        help="Collaborative candidate count requested per user.",
    )
    parser.add_argument(
        "--content-k",
        type=int,
        default=60,
        help="Content candidate count requested when the latest train anchor is enabled.",
    )
    parser.add_argument(
        "--blended-k",
        type=int,
        default=100,
        help="Blended candidate pool size before reranking.",
    )
    parser.add_argument(
        "--parquet-batch-size",
        type=int,
        default=250_000,
        help="Batch size used while streaming interactions_train.parquet.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=default_eval_paths.reports_dir,
        help="Directory where evaluation reports should be written.",
    )
    parser.add_argument(
        "--use-latest-train-anchor",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to pass the user's latest train purchase as anchor_product_id.",
    )
    parser.add_argument(
        "--apply-seen-filter-before-reranking",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Whether to remove train-seen products from the blended pool before "
            "offline reranking and metric computation."
        ),
    )
    parser.add_argument(
        "--log-every-users",
        type=int,
        default=250,
        help="Print evaluation progress every N users. Use 0 to disable progress logs.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> OfflineEvaluationConfig:
    metric_ks = parse_metric_ks(args.metric_ks)
    default_eval_paths = default_paths()
    eval_paths = OfflineEvaluationPaths(
        repo_root=default_eval_paths.repo_root,
        train_interactions_path=default_eval_paths.train_interactions_path,
        val_interactions_path=default_eval_paths.val_interactions_path,
        products_path=default_eval_paths.products_path,
        split_metadata_path=default_eval_paths.split_metadata_path,
        reports_dir=args.reports_dir,
    )
    config = OfflineEvaluationConfig(
        paths=eval_paths,
        metric_ks=metric_ks,
        report_k=args.report_k,
        max_users=args.max_users,
        sample_seed=args.sample_seed,
        parquet_batch_size=args.parquet_batch_size,
        collaborative_k=args.collaborative_k,
        content_k=args.content_k,
        blended_k=args.blended_k,
        use_latest_train_anchor=args.use_latest_train_anchor,
        apply_seen_filter_before_reranking=args.apply_seen_filter_before_reranking,
        log_every_users=args.log_every_users,
    )
    config.validate()
    return config


def build_summary_payload(
    config: OfflineEvaluationConfig,
    split_metadata: dict[str, object],
    total_validation_user_count: int,
    candidate_user_ids: list[str],
    user_profiles: list[object],
    selection_summary: dict[str, int],
    train_scan_artifacts,
    evaluation_result: dict[str, object],
) -> dict[str, object]:
    average_train_interactions = 0.0
    average_validation_targets = 0.0
    if user_profiles:
        average_train_interactions = sum(
            profile.train_interaction_count for profile in user_profiles
        ) / float(len(user_profiles))
        average_validation_targets = sum(
            len(profile.relevant_product_ids) for profile in user_profiles
        ) / float(len(user_profiles))

    return {
        "generated_at": utc_timestamp(),
        "phase": "phase_12_offline_evaluation",
        "evaluation_mode": "recommendation_only_purchase_holdout",
        "config": config.to_summary_dict(),
        "split_metadata": split_metadata,
        "user_selection": {
            "validation_user_count_total": total_validation_user_count,
            "candidate_validation_user_count_after_sampling": len(candidate_user_ids),
            **selection_summary,
            "average_train_interactions_per_user": average_train_interactions,
            "average_validation_targets_per_user": average_validation_targets,
        },
        "shared_candidate_generation": {
            "total_train_rows_scanned": train_scan_artifacts.total_train_rows,
            **evaluation_result["shared_candidate_stats"],
        },
        "assumptions": [
            (
                "The main benchmark uses recommendation-only inputs: user_id plus, "
                "optionally, the latest train purchase as a content anchor."
            ),
            "No query text is fabricated for offline evaluation.",
            "No session events are fabricated for offline evaluation.",
            (
                "When enabled, an evaluation-only seen-item filter removes products "
                "already present in the user's train history before reranking."
            ),
            (
                "Ground truth relevance is the set of distinct validation purchases "
                "for each evaluated user."
            ),
            (
                "Strategy comparison is run on the exact same user subset and the "
                "exact same blended candidate pool per user."
            ),
        ],
        "limitations": [
            (
                "This benchmark measures purchase-holdout recommendation quality, not "
                "true online engagement or business impact."
            ),
            (
                "Search intent is not directly evaluated because the validation labels "
                "do not contain grounded query text."
            ),
            (
                "Session intent is not directly evaluated because the validation labels "
                "do not contain grounded real-time browsing sequences."
            ),
            (
                "Explainability quality is not measured here because purchase logs do "
                "not validate explanation usefulness or truthfulness on their own."
            ),
        ],
        "strategy_results": evaluation_result["strategy_results"],
    }


def build_run_notes_markdown(
    summary_payload: dict[str, object],
    comparison_rows: list[dict[str, object]],
) -> str:
    split_metadata = summary_payload["split_metadata"]
    user_selection = summary_payload["user_selection"]
    candidate_stats = summary_payload["shared_candidate_generation"]
    config = summary_payload["config"]
    report_k = config["report_k"]

    top_strategy_lines = [
        (
            f"{index}. `{row['strategy_key']}` "
            f"(NDCG@{report_k}={row['ndcg_at_report_k']:.4f}, "
            f"Recall@{report_k}={row['recall_at_report_k']:.4f})"
        )
        for index, row in enumerate(comparison_rows, start=1)
    ]

    all_ndcg_values = {round(row["ndcg_at_report_k"], 8) for row in comparison_rows}
    tie_note = ""
    if len(all_ndcg_values) == 1:
        tie_note = (
            f"All compared strategies tied on NDCG@{report_k} in this run. "
            "That can happen because the benchmark does not inject query or session inputs.\n"
        )

    lines = [
        "# Offline Evaluation Notes",
        "",
        f"Generated at: `{summary_payload['generated_at']}`",
        "",
        "## What Was Evaluated",
        "",
        (
            "This run measures recommendation quality on the held-out validation "
            "purchases using the existing blending and reranking stack in a "
            "recommendation-only mode."
        ),
        (
            f"Validation window: `{split_metadata.get('val_min_date')}` to "
            f"`{split_metadata.get('val_max_date')}`."
        ),
        (
            f"Evaluated users: `{user_selection['evaluated_user_count']}` out of "
            f"`{user_selection['validation_user_count_total']}` validation users."
        ),
        "",
        "## Main Assumptions",
        "",
        "- `user_id` is always provided to the offline recommendation request.",
        (
            "- The latest train purchase is used as `anchor_product_id` when "
            f"`use_latest_train_anchor={config['use_latest_train_anchor']}`."
        ),
        "- No query text is fabricated.",
        "- No session events are fabricated.",
        (
            "- Train-seen products are removed before reranking when "
            f"`apply_seen_filter_before_reranking={config['apply_seen_filter_before_reranking']}`."
        ),
        (
            "- Relevance is the set of distinct validation purchases for each user, "
            "not the order of those purchases."
        ),
        "",
        "## What This Run Does Not Capture",
        "",
        "- It does not validate query understanding because the hold-out labels do not include search queries.",
        "- It does not validate session intent because the hold-out labels do not include real browsing sessions.",
        "- It does not validate explanation quality because purchase logs alone cannot score explanations.",
        "- It does not replace online testing, counterfactual evaluation, or product analytics from the persistence layer.",
        "",
        "## Candidate Pool Notes",
        "",
        (
            f"- Content source used rate: "
            f"`{candidate_stats['content_source_used_rate']:.4f}`."
        ),
        (
            f"- Collaborative popularity fallback rate: "
            f"`{candidate_stats['collaborative_popularity_fallback_rate']:.4f}`."
        ),
        (
            f"- Average candidates before seen filter: "
            f"`{candidate_stats['avg_candidates_before_seen_filter']:.2f}`."
        ),
        (
            f"- Average candidates after seen filter: "
            f"`{candidate_stats['avg_candidates_after_seen_filter']:.2f}`."
        ),
    ]
    if tie_note:
        lines.extend(["", tie_note.rstrip()])

    lines.extend(
        [
            "",
            "## Strategy Ranking",
            "",
            *top_strategy_lines,
            "",
            "## Interpretation",
            "",
            (
                "Use these results to compare stable strategy presets under the same "
                "historical purchase-holdout setup. Do not read the search-boosted or "
                "session-boosted rows as true search/session benchmarks, because those "
                "signals were intentionally not fabricated for this offline run."
            ),
        ]
    )
    return "\n".join(lines)


def write_reports(
    reports_dir: Path,
    summary_payload: dict[str, object],
    metrics_rows: list[dict[str, object]],
    comparison_rows: list[dict[str, object]],
) -> None:
    ensure_directory(reports_dir)

    summary_path = reports_dir / "offline_eval_summary.json"
    metrics_path = reports_dir / "offline_eval_metrics.csv"
    comparison_path = reports_dir / "strategy_comparison.csv"
    notes_path = reports_dir / "offline_eval_notes.md"

    write_json(summary_path, summary_payload)
    pd.DataFrame(metrics_rows).to_csv(metrics_path, index=False)
    pd.DataFrame(comparison_rows).to_csv(comparison_path, index=False)
    write_markdown(notes_path, build_run_notes_markdown(summary_payload, comparison_rows))


def main() -> int:
    args = parse_args()
    config = build_config(args)

    print("Loading validation targets...", flush=True)
    validation_targets = load_validation_targets(config.paths.val_interactions_path)
    total_validation_user_count = len(validation_targets)
    candidate_user_ids = select_candidate_user_ids(
        validation_targets=validation_targets,
        max_users=config.max_users,
        sample_seed=config.sample_seed,
    )
    candidate_validation_targets = {
        user_id: validation_targets[user_id]
        for user_id in candidate_user_ids
    }
    print(
        f"Selected {len(candidate_user_ids):,} candidate validation users "
        f"from {total_validation_user_count:,} total validation users.",
        flush=True,
    )

    print("Scanning train interactions for user history and product popularity...", flush=True)
    train_scan_artifacts = scan_train_histories(
        train_interactions_path=config.paths.train_interactions_path,
        target_user_ids=candidate_user_ids,
        batch_size=config.parquet_batch_size,
    )

    user_profiles, selection_summary = build_user_profiles(
        validation_targets=candidate_validation_targets,
        train_scan_artifacts=train_scan_artifacts,
    )
    if not user_profiles:
        raise ValueError("No evaluation users remained after applying the train-history filter.")

    print(
        f"Built {len(user_profiles):,} user evaluation profiles. "
        f"Dropped {selection_summary['dropped_missing_train_history_count']:,} "
        "users without train history.",
        flush=True,
    )

    catalog_size = load_catalog_size(config.paths.products_path)
    split_metadata = load_json(config.paths.split_metadata_path)

    print("Evaluating strategies on the shared candidate pools...", flush=True)
    evaluation_result = evaluate_strategies(
        config=config,
        user_profiles=user_profiles,
        catalog_size=catalog_size,
        popularity_by_product=train_scan_artifacts.product_popularity_by_id,
    )

    summary_payload = build_summary_payload(
        config=config,
        split_metadata=split_metadata,
        total_validation_user_count=total_validation_user_count,
        candidate_user_ids=candidate_user_ids,
        user_profiles=user_profiles,
        selection_summary=selection_summary,
        train_scan_artifacts=train_scan_artifacts,
        evaluation_result=evaluation_result,
    )
    write_reports(
        reports_dir=config.paths.reports_dir,
        summary_payload=summary_payload,
        metrics_rows=evaluation_result["metrics_rows"],
        comparison_rows=evaluation_result["comparison_rows"],
    )

    comparison_frame = pd.DataFrame(evaluation_result["comparison_rows"])
    display_columns = [
        "strategy_key",
        "report_k",
        "precision_at_report_k",
        "recall_at_report_k",
        "ndcg_at_report_k",
        "catalog_coverage_at_report_k",
        "avg_recommendation_popularity_at_report_k",
    ]
    print("Offline evaluation complete.", flush=True)
    print(comparison_frame[display_columns].to_string(index=False), flush=True)
    print(f"Reports written to: {config.paths.reports_dir.as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
