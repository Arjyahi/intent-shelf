from dataclasses import dataclass
from functools import lru_cache

from app.schemas.retrieval import (
    RANKING_STRATEGY_DEFAULT,
    RANKING_STRATEGY_DIVERSITY_BOOSTED,
    RANKING_STRATEGY_SEARCH_INTENT_BOOSTED,
    RANKING_STRATEGY_SESSION_BOOSTED,
    RankingStrategiesResponse,
    RankingStrategyDefinition,
    RankingStrategyResolution,
    RankingStrategySummary,
    RerankingConfig,
    RerankingDiversityConfig,
    RerankingFeatureWeights,
)


def build_default_ranking_strategies() -> list[RankingStrategyDefinition]:
    """Return the small explicit strategy set used by the Phase 10 reranker."""

    return [
        RankingStrategyDefinition(
            key=RANKING_STRATEGY_DEFAULT,
            name="Default",
            description=(
                "Balanced reranking across blended score, search, session, "
                "collaborative support, and modest diversity."
            ),
            config=RerankingConfig(),
        ),
        RankingStrategyDefinition(
            key=RANKING_STRATEGY_SEARCH_INTENT_BOOSTED,
            name="Search Intent Boosted",
            description=(
                "Raises search-related weights when explicit query intent should "
                "have more influence on the final order."
            ),
            config=RerankingConfig(
                feature_weights=RerankingFeatureWeights(
                    blended_score=1.0,
                    search_signal=0.85,
                    search_presence=0.3,
                    session_signal=0.3,
                    session_presence=0.08,
                    content_signal=0.2,
                    collaborative_signal=0.1,
                    popularity_signal=0.05,
                    multi_source_signal=0.2,
                    exact_anchor_penalty=0.6,
                ),
                diversity=RerankingDiversityConfig(
                    enabled=True,
                    apply_top_n=10,
                    product_type_penalty=0.25,
                    product_group_penalty=0.1,
                    max_penalty=0.75,
                ),
            ),
        ),
        RankingStrategyDefinition(
            key=RANKING_STRATEGY_SESSION_BOOSTED,
            name="Session Boosted",
            description=(
                "Raises session-related weights so recent browsing activity has "
                "stronger influence on the final order."
            ),
            config=RerankingConfig(
                feature_weights=RerankingFeatureWeights(
                    blended_score=1.0,
                    search_signal=0.25,
                    search_presence=0.05,
                    session_signal=0.9,
                    session_presence=0.35,
                    content_signal=0.25,
                    collaborative_signal=0.12,
                    popularity_signal=0.05,
                    multi_source_signal=0.25,
                    exact_anchor_penalty=0.5,
                ),
                diversity=RerankingDiversityConfig(),
            ),
        ),
        RankingStrategyDefinition(
            key=RANKING_STRATEGY_DIVERSITY_BOOSTED,
            name="Diversity Boosted",
            description=(
                "Keeps the same reranking pipeline but applies stronger diversity "
                "penalties in the early ranked positions."
            ),
            config=RerankingConfig(
                feature_weights=RerankingFeatureWeights(
                    blended_score=0.95,
                    search_signal=0.35,
                    search_presence=0.1,
                    session_signal=0.4,
                    session_presence=0.12,
                    content_signal=0.18,
                    collaborative_signal=0.12,
                    popularity_signal=0.08,
                    multi_source_signal=0.25,
                    exact_anchor_penalty=0.5,
                ),
                diversity=RerankingDiversityConfig(
                    enabled=True,
                    apply_top_n=16,
                    product_type_penalty=0.5,
                    product_group_penalty=0.2,
                    max_penalty=1.2,
                ),
            ),
        ),
    ]


@dataclass(frozen=True)
class ResolvedRankingStrategy:
    requested_key: str
    definition: RankingStrategyDefinition
    used_fallback: bool = False

    def to_schema(self) -> RankingStrategyResolution:
        return RankingStrategyResolution(
            requested_key=self.requested_key,
            resolved_key=self.definition.key,
            used_fallback=self.used_fallback,
            strategy=RankingStrategySummary(
                key=self.definition.key,
                name=self.definition.name,
                description=self.definition.description,
            ),
        )


class RankingStrategyRegistry:
    """Central registry for the small set of inspectable ranking strategies."""

    def __init__(
        self,
        strategies: list[RankingStrategyDefinition] | None = None,
        default_strategy_key: str = RANKING_STRATEGY_DEFAULT,
    ) -> None:
        strategy_definitions = strategies or build_default_ranking_strategies()
        if not strategy_definitions:
            raise ValueError("RankingStrategyRegistry requires at least one strategy.")

        self._strategy_order = [definition.key for definition in strategy_definitions]
        self._strategies_by_key = {
            definition.key: definition.model_copy(deep=True)
            for definition in strategy_definitions
        }
        if default_strategy_key not in self._strategies_by_key:
            raise ValueError(
                f"Unknown default ranking strategy: {default_strategy_key}"
            )
        self.default_strategy_key = default_strategy_key

    def list_strategies(self) -> list[RankingStrategyDefinition]:
        return [
            self._strategies_by_key[key].model_copy(deep=True)
            for key in self._strategy_order
        ]

    def get_strategy(self, key: str) -> RankingStrategyDefinition | None:
        strategy = self._strategies_by_key.get(key)
        if strategy is None:
            return None
        return strategy.model_copy(deep=True)

    def get_default_strategy(self) -> RankingStrategyDefinition:
        return self._strategies_by_key[self.default_strategy_key].model_copy(deep=True)

    def resolve_strategy(self, key: str | None) -> ResolvedRankingStrategy:
        normalized_key = key or self.default_strategy_key
        strategy = self.get_strategy(normalized_key)
        if strategy is not None:
            return ResolvedRankingStrategy(
                requested_key=normalized_key,
                definition=strategy,
                used_fallback=False,
            )

        return ResolvedRankingStrategy(
            requested_key=normalized_key,
            definition=self.get_default_strategy(),
            used_fallback=True,
        )

    def build_response(self) -> RankingStrategiesResponse:
        return RankingStrategiesResponse(
            default_strategy_key=self.default_strategy_key,
            strategies=self.list_strategies(),
        )


@lru_cache(maxsize=1)
def get_ranking_strategy_registry() -> RankingStrategyRegistry:
    return RankingStrategyRegistry()
