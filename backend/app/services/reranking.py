from dataclasses import dataclass
from functools import lru_cache

from app.schemas.retrieval import (
    BlendedCandidate,
    BlendedCandidatesRequest,
    BlendedCandidatesResponse,
    BlendedSourceSummary,
    FeedRerankRequest,
    FeedRerankResponse,
    RerankedCandidate,
    RerankingConfig,
    RerankingConfigOverrides,
    RerankingDiversityConfig,
    RerankingFeatureSummary,
    RerankingFeatureWeights,
    RerankingScoreBreakdown,
)
from app.services.candidate_blending import CandidateBlendingService, get_candidate_blending_service
from app.services.ranking_strategies import (
    RankingStrategyRegistry,
    get_ranking_strategy_registry,
)

SOURCE_COLLABORATIVE = "collaborative"
SOURCE_CONTENT = "content"
SOURCE_SEARCH = "search"
SOURCE_SESSION = "session"

MAX_CONTRIBUTING_SOURCES = 4


@dataclass(frozen=True)
class StaticRerankingFeatures:
    blended_score: float
    search_signal: float
    search_presence: float
    session_signal: float
    session_presence: float
    content_signal: float
    collaborative_signal: float
    popularity_signal: float
    multi_source_signal: float
    exact_anchor_penalty: float
    source_count: int


@dataclass(frozen=True)
class BaseScoreState:
    candidate: BlendedCandidate
    features: StaticRerankingFeatures
    base_score: float
    blended_component: float
    search_component: float
    search_presence_component: float
    session_component: float
    session_presence_component: float
    content_component: float
    collaborative_component: float
    popularity_component: float
    multi_source_component: float
    exact_anchor_penalty_component: float


@dataclass(frozen=True)
class DiversityPenaltyState:
    penalty: float
    repeated_product_type_count: int
    repeated_product_group_count: int


class FeedRerankingService:
    """
    Phase 8 heuristic reranking service.

    This layer reuses the Phase 7 blended candidate pool, extracts simple
    transparent ranking features, computes a weighted base score, and then
    applies a readable diversity penalty while building the final order.
    """

    def __init__(
        self,
        candidate_blending_service: CandidateBlendingService | None = None,
        strategy_registry: RankingStrategyRegistry | None = None,
    ) -> None:
        self.candidate_blending_service = (
            candidate_blending_service or get_candidate_blending_service()
        )
        self.strategy_registry = strategy_registry or get_ranking_strategy_registry()

    def rerank_feed(
        self,
        request: FeedRerankRequest,
    ) -> FeedRerankResponse:
        blend_request = self._build_blend_request(request)
        blended_response = self.candidate_blending_service.blend_candidates(blend_request)
        return self.rerank_preblended_candidates(
            request=request,
            blended_response=blended_response,
        )

    def rerank_preblended_candidates(
        self,
        request: FeedRerankRequest,
        blended_response: BlendedCandidatesResponse,
    ) -> FeedRerankResponse:
        """
        Rerank an already prepared blended candidate pool.

        The API path still uses `rerank_feed()`, but offline evaluation can call
        this method so the same blended candidates are reused across multiple
        strategy comparisons instead of re-running retrieval for every strategy.
        """

        strategy_resolution = self.strategy_registry.resolve_strategy(request.ranking_strategy)
        effective_config = self._build_effective_config(
            base_config=strategy_resolution.definition.config,
            overrides=request.reranking_overrides,
        )
        resolved_strategy_key = strategy_resolution.definition.key
        reranked_k = request.reranked_k or request.blended_k

        if not blended_response.results:
            return FeedRerankResponse(
                ranking_strategy=resolved_strategy_key,
                requested_ranking_strategy=request.ranking_strategy,
                strategy_resolution=strategy_resolution.to_schema(),
                reranked_k=reranked_k,
                blended_candidate_count=0,
                returned_candidate_count=0,
                normalization_strategy=blended_response.normalization_strategy,
                dedup_key=blended_response.dedup_key,
                used_sources=blended_response.used_sources,
                source_weights=blended_response.source_weights,
                effective_reranking_config=effective_config,
                message=blended_response.message or "No blended candidates available for reranking.",
                source_summaries=blended_response.source_summaries,
                results=[],
            )

        base_states = self._score_blended_candidates(
            blended_response=blended_response,
            request=request,
            config=effective_config,
        )
        reranked_results = self._build_reranked_results(
            base_states=base_states,
            ranking_strategy=resolved_strategy_key,
            reranked_k=reranked_k,
            diversity_config=effective_config.diversity,
        )

        return FeedRerankResponse(
            ranking_strategy=resolved_strategy_key,
            requested_ranking_strategy=request.ranking_strategy,
            strategy_resolution=strategy_resolution.to_schema(),
            reranked_k=reranked_k,
            blended_candidate_count=len(blended_response.results),
            returned_candidate_count=len(reranked_results),
            normalization_strategy=blended_response.normalization_strategy,
            dedup_key=blended_response.dedup_key,
            used_sources=blended_response.used_sources,
            source_weights=blended_response.source_weights,
            effective_reranking_config=effective_config,
            message=None,
            source_summaries=blended_response.source_summaries,
            results=reranked_results,
        )

    @staticmethod
    def _build_blend_request(request: FeedRerankRequest) -> BlendedCandidatesRequest:
        request_payload = request.model_dump(
            exclude={
                "ranking_strategy",
                "reranked_k",
                "reranking_overrides",
            }
        )
        return BlendedCandidatesRequest.model_validate(request_payload)

    @staticmethod
    def _build_effective_config(
        base_config: RerankingConfig,
        overrides: RerankingConfigOverrides | None,
    ) -> RerankingConfig:
        base_config = base_config.model_copy(deep=True)
        if overrides is None:
            return base_config

        feature_weights = base_config.feature_weights
        if overrides.feature_weights is not None:
            feature_weights = feature_weights.model_copy(
                update=overrides.feature_weights.model_dump(exclude_none=True)
            )

        diversity = base_config.diversity
        if overrides.diversity is not None:
            diversity = diversity.model_copy(
                update=overrides.diversity.model_dump(exclude_none=True)
            )

        return RerankingConfig(
            feature_weights=feature_weights,
            diversity=diversity,
        )

    def _score_blended_candidates(
        self,
        blended_response: BlendedCandidatesResponse,
        request: FeedRerankRequest,
        config: RerankingConfig,
    ) -> list[BaseScoreState]:
        collaborative_summary = self._get_source_summary(
            source_summaries=blended_response.source_summaries,
            source=SOURCE_COLLABORATIVE,
        )
        collaborative_is_popularity = (
            collaborative_summary is not None
            and collaborative_summary.score_label == "global_popularity"
        )
        has_query = bool(request.query)
        has_session_context = bool(
            request.session_events or request.like_events or request.save_events
        )

        base_states: list[BaseScoreState] = []
        for candidate in blended_response.results:
            static_features = self._extract_static_features(
                candidate=candidate,
                anchor_product_id=request.anchor_product_id,
                has_query=has_query,
                has_session_context=has_session_context,
                collaborative_is_popularity=collaborative_is_popularity,
            )
            base_states.append(
                self._compute_base_score(
                    candidate=candidate,
                    features=static_features,
                    weights=config.feature_weights,
                )
            )

        return base_states

    @staticmethod
    def _get_source_summary(
        source_summaries: list[BlendedSourceSummary],
        source: str,
    ) -> BlendedSourceSummary | None:
        for source_summary in source_summaries:
            if source_summary.source == source:
                return source_summary
        return None

    @staticmethod
    def _extract_static_features(
        candidate: BlendedCandidate,
        anchor_product_id: str | None,
        has_query: bool,
        has_session_context: bool,
        collaborative_is_popularity: bool,
    ) -> StaticRerankingFeatures:
        source_count = len(candidate.contributing_sources)
        max_multi_source_denominator = max(MAX_CONTRIBUTING_SOURCES - 1, 1)
        multi_source_signal = max(
            0.0,
            min(source_count - 1, max_multi_source_denominator) / max_multi_source_denominator,
        )

        search_signal = candidate.normalized_source_scores.get(SOURCE_SEARCH, 0.0)
        session_signal = candidate.normalized_source_scores.get(SOURCE_SESSION, 0.0)
        content_signal = candidate.normalized_source_scores.get(SOURCE_CONTENT, 0.0)
        collaborative_signal = candidate.normalized_source_scores.get(
            SOURCE_COLLABORATIVE,
            0.0,
        )
        popularity_signal = collaborative_signal if collaborative_is_popularity else 0.0
        exact_anchor_penalty = (
            1.0 if anchor_product_id is not None and candidate.product_id == anchor_product_id else 0.0
        )

        return StaticRerankingFeatures(
            blended_score=candidate.blended_score,
            search_signal=search_signal,
            search_presence=1.0 if has_query and search_signal > 0.0 else 0.0,
            session_signal=session_signal,
            session_presence=1.0 if has_session_context and session_signal > 0.0 else 0.0,
            content_signal=content_signal,
            collaborative_signal=collaborative_signal,
            popularity_signal=popularity_signal,
            multi_source_signal=multi_source_signal,
            exact_anchor_penalty=exact_anchor_penalty,
            source_count=source_count,
        )

    @staticmethod
    def _compute_base_score(
        candidate: BlendedCandidate,
        features: StaticRerankingFeatures,
        weights: RerankingFeatureWeights,
    ) -> BaseScoreState:
        blended_component = weights.blended_score * features.blended_score
        search_component = weights.search_signal * features.search_signal
        search_presence_component = weights.search_presence * features.search_presence
        session_component = weights.session_signal * features.session_signal
        session_presence_component = weights.session_presence * features.session_presence
        content_component = weights.content_signal * features.content_signal
        collaborative_component = weights.collaborative_signal * features.collaborative_signal
        popularity_component = weights.popularity_signal * features.popularity_signal
        multi_source_component = weights.multi_source_signal * features.multi_source_signal
        exact_anchor_penalty_component = (
            weights.exact_anchor_penalty * features.exact_anchor_penalty
        )

        base_score = (
            blended_component
            + search_component
            + search_presence_component
            + session_component
            + session_presence_component
            + content_component
            + collaborative_component
            + popularity_component
            + multi_source_component
            - exact_anchor_penalty_component
        )

        return BaseScoreState(
            candidate=candidate,
            features=features,
            base_score=base_score,
            blended_component=blended_component,
            search_component=search_component,
            search_presence_component=search_presence_component,
            session_component=session_component,
            session_presence_component=session_presence_component,
            content_component=content_component,
            collaborative_component=collaborative_component,
            popularity_component=popularity_component,
            multi_source_component=multi_source_component,
            exact_anchor_penalty_component=exact_anchor_penalty_component,
        )

    def _build_reranked_results(
        self,
        base_states: list[BaseScoreState],
        ranking_strategy: str,
        reranked_k: int,
        diversity_config: RerankingDiversityConfig,
    ) -> list[RerankedCandidate]:
        remaining_states = list(base_states)
        selected_results: list[RerankedCandidate] = []

        while remaining_states and len(selected_results) < reranked_k:
            scored_candidates: list[tuple[float, float, float, str, BaseScoreState, DiversityPenaltyState]] = []
            for base_state in remaining_states:
                diversity_state = self._compute_diversity_penalty(
                    candidate=base_state.candidate,
                    selected_results=selected_results,
                    diversity_config=diversity_config,
                )
                reranked_score = base_state.base_score - diversity_state.penalty
                scored_candidates.append(
                    (
                        reranked_score,
                        base_state.base_score,
                        base_state.candidate.blended_score,
                        base_state.candidate.product_id,
                        base_state,
                        diversity_state,
                    )
                )

            scored_candidates.sort(
                key=lambda item: (-item[0], -item[1], -item[2], item[3])
            )
            (
                reranked_score,
                _base_score,
                _blended_score,
                chosen_product_id,
                chosen_base_state,
                chosen_diversity_state,
            ) = scored_candidates[0]

            selected_results.append(
                self._build_reranked_candidate(
                    base_state=chosen_base_state,
                    diversity_state=chosen_diversity_state,
                    reranked_score=reranked_score,
                    ranking_strategy=ranking_strategy,
                    ranking_position=len(selected_results) + 1,
                )
            )
            remaining_states = [
                base_state
                for base_state in remaining_states
                if base_state.candidate.product_id != chosen_product_id
            ]

        return selected_results

    @staticmethod
    def _compute_diversity_penalty(
        candidate: BlendedCandidate,
        selected_results: list[RerankedCandidate],
        diversity_config: RerankingDiversityConfig,
    ) -> DiversityPenaltyState:
        if not diversity_config.enabled:
            return DiversityPenaltyState(
                penalty=0.0,
                repeated_product_type_count=0,
                repeated_product_group_count=0,
            )

        if len(selected_results) >= diversity_config.apply_top_n:
            return DiversityPenaltyState(
                penalty=0.0,
                repeated_product_type_count=0,
                repeated_product_group_count=0,
            )

        repeated_product_type_count = 0
        repeated_product_group_count = 0

        for selected_result in selected_results:
            if (
                candidate.product_type_name
                and selected_result.product_type_name == candidate.product_type_name
            ):
                repeated_product_type_count += 1
            if (
                candidate.product_group_name
                and selected_result.product_group_name == candidate.product_group_name
            ):
                repeated_product_group_count += 1

        penalty = min(
            (
                repeated_product_type_count * diversity_config.product_type_penalty
                + repeated_product_group_count * diversity_config.product_group_penalty
            ),
            diversity_config.max_penalty,
        )
        return DiversityPenaltyState(
            penalty=penalty,
            repeated_product_type_count=repeated_product_type_count,
            repeated_product_group_count=repeated_product_group_count,
        )

    @staticmethod
    def _build_reranked_candidate(
        base_state: BaseScoreState,
        diversity_state: DiversityPenaltyState,
        reranked_score: float,
        ranking_strategy: str,
        ranking_position: int,
    ) -> RerankedCandidate:
        reranking_features = RerankingFeatureSummary(
            blended_score=base_state.features.blended_score,
            search_signal=base_state.features.search_signal,
            search_presence=base_state.features.search_presence,
            session_signal=base_state.features.session_signal,
            session_presence=base_state.features.session_presence,
            content_signal=base_state.features.content_signal,
            collaborative_signal=base_state.features.collaborative_signal,
            popularity_signal=base_state.features.popularity_signal,
            multi_source_signal=base_state.features.multi_source_signal,
            exact_anchor_penalty=base_state.features.exact_anchor_penalty,
            diversity_penalty=diversity_state.penalty,
            source_count=base_state.features.source_count,
            repeated_product_type_count=diversity_state.repeated_product_type_count,
            repeated_product_group_count=diversity_state.repeated_product_group_count,
        )
        score_breakdown = RerankingScoreBreakdown(
            blended_component=base_state.blended_component,
            search_component=base_state.search_component,
            search_presence_component=base_state.search_presence_component,
            session_component=base_state.session_component,
            session_presence_component=base_state.session_presence_component,
            content_component=base_state.content_component,
            collaborative_component=base_state.collaborative_component,
            popularity_component=base_state.popularity_component,
            multi_source_component=base_state.multi_source_component,
            exact_anchor_penalty_component=base_state.exact_anchor_penalty_component,
            diversity_penalty_component=diversity_state.penalty,
        )

        candidate = base_state.candidate
        return RerankedCandidate(
            product_id=candidate.product_id,
            product_name=candidate.product_name,
            product_type_name=candidate.product_type_name,
            product_group_name=candidate.product_group_name,
            colour_group_name=candidate.colour_group_name,
            department_name=candidate.department_name,
            image_path=candidate.image_path,
            has_image=candidate.has_image,
            blended_score=candidate.blended_score,
            contributing_sources=candidate.contributing_sources,
            raw_source_scores=candidate.raw_source_scores,
            normalized_source_scores=candidate.normalized_source_scores,
            weighted_source_scores=candidate.weighted_source_scores,
            source_rank_positions=candidate.source_rank_positions,
            source_weights=candidate.source_weights,
            ranking_position=ranking_position,
            reranked_score=reranked_score,
            base_reranking_score=base_state.base_score,
            ranking_strategy=ranking_strategy,
            reranking_features=reranking_features,
            score_breakdown=score_breakdown,
        )


@lru_cache(maxsize=1)
def get_feed_reranking_service() -> FeedRerankingService:
    return FeedRerankingService()
