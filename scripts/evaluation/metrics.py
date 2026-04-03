from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


def precision_at_k(
    recommended_product_ids: Sequence[str],
    relevant_product_ids: set[str],
    k: int,
) -> float:
    if k <= 0:
        raise ValueError("k must be positive for precision_at_k.")
    hits = sum(1 for product_id in recommended_product_ids[:k] if product_id in relevant_product_ids)
    return hits / float(k)


def recall_at_k(
    recommended_product_ids: Sequence[str],
    relevant_product_ids: set[str],
    k: int,
) -> float:
    if not relevant_product_ids:
        return 0.0
    hits = sum(1 for product_id in recommended_product_ids[:k] if product_id in relevant_product_ids)
    return hits / float(len(relevant_product_ids))


def ndcg_at_k(
    recommended_product_ids: Sequence[str],
    relevant_product_ids: set[str],
    k: int,
) -> float:
    if k <= 0:
        raise ValueError("k must be positive for ndcg_at_k.")
    if not relevant_product_ids:
        return 0.0

    dcg = 0.0
    for rank, product_id in enumerate(recommended_product_ids[:k], start=1):
        if product_id in relevant_product_ids:
            dcg += 1.0 / _log2(rank + 1)

    ideal_hit_count = min(len(relevant_product_ids), k)
    if ideal_hit_count == 0:
        return 0.0

    ideal_dcg = sum(1.0 / _log2(rank + 1) for rank in range(1, ideal_hit_count + 1))
    return dcg / ideal_dcg if ideal_dcg > 0.0 else 0.0


def repeated_value_ratio(values: Sequence[str | None]) -> float:
    if not values:
        return 0.0

    present_values = [value for value in values if value not in (None, "")]
    if len(present_values) <= 1:
        return 0.0

    duplicate_count = len(present_values) - len(set(present_values))
    return duplicate_count / float(len(values))


def _log2(value: float) -> float:
    import math

    return math.log2(value)


@dataclass
class MetricAccumulator:
    """
    Collect aggregate offline metrics for one strategy at one cutoff.

    The implementation is intentionally plain:
    - ranking metrics are averaged per user
    - coverage is computed from the union of recommended items
    - popularity and diversity are averaged over the returned recommendation slots
    """

    k: int
    catalog_size: int
    popularity_by_product: Mapping[str, int]
    user_count: int = 0
    precision_sum: float = 0.0
    recall_sum: float = 0.0
    ndcg_sum: float = 0.0
    returned_count_sum: int = 0
    popularity_sum: float = 0.0
    popularity_observation_count: int = 0
    repeated_product_type_ratio_sum: float = 0.0
    repeated_product_group_ratio_sum: float = 0.0
    recommended_product_ids: set[str] = field(default_factory=set)

    def update(
        self,
        recommendations: Sequence[object],
        relevant_product_ids: set[str],
    ) -> None:
        top_results = list(recommendations[: self.k])
        recommended_product_ids = [
            str(getattr(result, "product_id"))
            for result in top_results
        ]

        self.user_count += 1
        self.precision_sum += precision_at_k(recommended_product_ids, relevant_product_ids, self.k)
        self.recall_sum += recall_at_k(recommended_product_ids, relevant_product_ids, self.k)
        self.ndcg_sum += ndcg_at_k(recommended_product_ids, relevant_product_ids, self.k)
        self.returned_count_sum += len(top_results)
        self.recommended_product_ids.update(recommended_product_ids)

        if top_results:
            self.popularity_sum += sum(
                float(self.popularity_by_product.get(product_id, 0))
                for product_id in recommended_product_ids
            )
            self.popularity_observation_count += len(top_results)
            self.repeated_product_type_ratio_sum += repeated_value_ratio(
                [getattr(result, "product_type_name", None) for result in top_results]
            )
            self.repeated_product_group_ratio_sum += repeated_value_ratio(
                [getattr(result, "product_group_name", None) for result in top_results]
            )

    def finalize(self) -> dict[str, object]:
        if self.user_count == 0:
            raise ValueError("Cannot finalize metrics without any evaluated users.")

        coverage = 0.0
        if self.catalog_size > 0:
            coverage = len(self.recommended_product_ids) / float(self.catalog_size)

        average_popularity = 0.0
        if self.popularity_observation_count > 0:
            average_popularity = self.popularity_sum / float(self.popularity_observation_count)

        return {
            "k": self.k,
            "user_count": self.user_count,
            "precision_at_k": self.precision_sum / float(self.user_count),
            "recall_at_k": self.recall_sum / float(self.user_count),
            "ndcg_at_k": self.ndcg_sum / float(self.user_count),
            "catalog_coverage_at_k": coverage,
            "avg_recommendation_popularity_at_k": average_popularity,
            "avg_repeated_product_type_ratio_at_k": (
                self.repeated_product_type_ratio_sum / float(self.user_count)
            ),
            "avg_repeated_product_group_ratio_at_k": (
                self.repeated_product_group_ratio_sum / float(self.user_count)
            ),
            "avg_returned_count_at_k": self.returned_count_sum / float(self.user_count),
            "unique_recommended_items_at_k": len(self.recommended_product_ids),
        }
