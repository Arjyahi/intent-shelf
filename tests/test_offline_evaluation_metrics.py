from types import SimpleNamespace

import pytest

from scripts.evaluation.metrics import (
    MetricAccumulator,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    repeated_value_ratio,
)


def test_basic_ranking_metrics_match_known_values() -> None:
    recommended_product_ids = ["a", "b", "c"]
    relevant_product_ids = {"b", "d"}

    assert precision_at_k(recommended_product_ids, relevant_product_ids, 3) == pytest.approx(1 / 3)
    assert recall_at_k(recommended_product_ids, relevant_product_ids, 3) == pytest.approx(0.5)
    assert ndcg_at_k(recommended_product_ids, relevant_product_ids, 3) == pytest.approx(
        0.3868528072
    )


def test_repeated_value_ratio_is_zero_for_missing_values_only() -> None:
    assert repeated_value_ratio([None, "", None]) == pytest.approx(0.0)
    assert repeated_value_ratio(["Top", "Top", "Dress"]) == pytest.approx(1 / 3)


def test_metric_accumulator_tracks_catalog_popularity_and_diversity() -> None:
    recommendations = [
        SimpleNamespace(product_id="a", product_type_name="Top", product_group_name="Upper body"),
        SimpleNamespace(product_id="b", product_type_name="Top", product_group_name="Upper body"),
        SimpleNamespace(product_id="c", product_type_name="Dress", product_group_name="Full body"),
    ]
    accumulator = MetricAccumulator(
        k=3,
        catalog_size=10,
        popularity_by_product={"a": 10, "b": 5, "c": 1},
    )

    accumulator.update(recommendations=recommendations, relevant_product_ids={"b", "x"})
    metrics = accumulator.finalize()

    assert metrics["precision_at_k"] == pytest.approx(1 / 3)
    assert metrics["recall_at_k"] == pytest.approx(0.5)
    assert metrics["catalog_coverage_at_k"] == pytest.approx(0.3)
    assert metrics["avg_recommendation_popularity_at_k"] == pytest.approx((10 + 5 + 1) / 3)
    assert metrics["avg_repeated_product_type_ratio_at_k"] == pytest.approx(1 / 3)
    assert metrics["avg_repeated_product_group_ratio_at_k"] == pytest.approx(1 / 3)
    assert metrics["avg_returned_count_at_k"] == pytest.approx(3.0)
