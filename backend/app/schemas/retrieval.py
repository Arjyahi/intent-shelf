from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.schemas.common import IntentShelfSchema
from app.schemas.events import LikeEvent, SaveEvent, Session, SessionEvent

RANKING_STRATEGY_DEFAULT = "default"
RANKING_STRATEGY_SEARCH_INTENT_BOOSTED = "search_intent_boosted"
RANKING_STRATEGY_SESSION_BOOSTED = "session_boosted"
RANKING_STRATEGY_DIVERSITY_BOOSTED = "diversity_boosted"


class SimilarProduct(IntentShelfSchema):
    """One similar-item result returned from the multimodal content index."""

    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_type_name: str | None = None
    product_group_name: str | None = None
    image_path: str | None = None
    has_image: bool = False
    score: float


class SimilarProductsResponse(IntentShelfSchema):
    """Response payload for GET /products/{product_id}/similar."""

    model_config = ConfigDict(protected_namespaces=())

    query_product_id: str = Field(..., min_length=1)
    k: int = Field(..., ge=1)
    model_name: str | None = None
    fusion_alpha: float | None = None
    results: list[SimilarProduct]


class CollaborativeRecommendation(IntentShelfSchema):
    """One product candidate returned by collaborative retrieval."""

    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_type_name: str | None = None
    product_group_name: str | None = None
    image_path: str | None = None
    has_image: bool = False
    score: float


class CollaborativeRecommendationsResponse(IntentShelfSchema):
    """Response payload for GET /users/{user_id}/recommendations/collaborative."""

    model_config = ConfigDict(protected_namespaces=())

    query_user_id: str = Field(..., min_length=1)
    k: int = Field(..., ge=1)
    model_name: str | None = None
    model_loss: str | None = None
    exclude_seen_items: bool = True
    is_known_user: bool
    score_source: str = Field(..., min_length=1)
    fallback_strategy: str | None = None
    message: str | None = None
    results: list[CollaborativeRecommendation]


class SearchResult(IntentShelfSchema):
    """One product candidate returned by lexical search retrieval."""

    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_type_name: str | None = None
    product_group_name: str | None = None
    colour_group_name: str | None = None
    department_name: str | None = None
    image_path: str | None = None
    has_image: bool = False
    score: float


class SearchResultsResponse(IntentShelfSchema):
    """Response payload for GET /search."""

    model_config = ConfigDict(protected_namespaces=())

    query: str
    normalized_query: str
    k: int = Field(..., ge=1)
    retrieval_method: str | None = None
    scoring_method: str | None = None
    indexed_fields: list[str]
    message: str | None = None
    results: list[SearchResult]


class SessionRecommendationsRequest(IntentShelfSchema):
    """Request payload for POST /sessions/recommendations."""

    session: Session | None = None
    session_events: list[SessionEvent] = Field(default_factory=list)
    like_events: list[LikeEvent] = Field(default_factory=list)
    save_events: list[SaveEvent] = Field(default_factory=list)
    k: int = Field(default=20, ge=1, le=100)
    max_recent_events: int | None = Field(default=None, ge=1, le=50)
    exclude_recent_products: bool = True


class SessionSignalSummary(IntentShelfSchema):
    """One usable session signal that contributed to the session embedding."""

    event_id: str = Field(..., min_length=1)
    signal_type: str = Field(..., min_length=1)
    product_id: str = Field(..., min_length=1)
    event_timestamp: datetime
    weight: float = Field(..., gt=0)


class SessionRecommendation(IntentShelfSchema):
    """One product candidate returned by session retrieval."""

    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_type_name: str | None = None
    product_group_name: str | None = None
    colour_group_name: str | None = None
    department_name: str | None = None
    image_path: str | None = None
    has_image: bool = False
    score: float


class SessionRecommendationsResponse(IntentShelfSchema):
    """Response payload for POST /sessions/recommendations."""

    model_config = ConfigDict(protected_namespaces=())

    query_session_id: str | None = None
    k: int = Field(..., ge=1)
    retrieval_method: str | None = None
    score_source: str = Field(..., min_length=1)
    model_name: str | None = None
    fusion_alpha: float | None = None
    max_recent_events: int = Field(..., ge=1)
    exclude_recent_products: bool = True
    usable_signal_count: int = Field(default=0, ge=0)
    ignored_event_count: int = Field(default=0, ge=0)
    unknown_product_ids: list[str] = Field(default_factory=list)
    used_product_ids: list[str] = Field(default_factory=list)
    supported_signal_types: list[str] = Field(default_factory=list)
    message: str | None = None
    used_signals: list[SessionSignalSummary] = Field(default_factory=list)
    results: list[SessionRecommendation] = Field(default_factory=list)


class BlendingSourceWeights(IntentShelfSchema):
    """
    First-pass source weights for Phase 7 candidate blending.

    These weights are intentionally simple and easy to inspect. They are not
    learned and they are not meant to replace a real reranker.
    """

    collaborative: float = Field(default=1.0, ge=0.0)
    session: float = Field(default=1.2, ge=0.0)
    search: float = Field(default=1.3, ge=0.0)
    content: float = Field(default=0.9, ge=0.0)


class BlendedCandidatesRequest(IntentShelfSchema):
    """Request payload for POST /candidates/blend."""

    user_id: str | None = None
    query: str | None = None
    anchor_product_id: str | None = None
    session: Session | None = None
    session_events: list[SessionEvent] = Field(default_factory=list)
    like_events: list[LikeEvent] = Field(default_factory=list)
    save_events: list[SaveEvent] = Field(default_factory=list)
    collaborative_k: int = Field(default=20, ge=1, le=100)
    content_k: int = Field(default=12, ge=1, le=100)
    search_k: int = Field(default=20, ge=1, le=100)
    session_k: int = Field(default=20, ge=1, le=100)
    blended_k: int = Field(default=40, ge=1, le=200)
    exclude_seen_items: bool = True
    max_recent_events: int | None = Field(default=None, ge=1, le=50)
    exclude_recent_products: bool = True
    normalization_strategy: Literal["min_max"] = "min_max"
    source_weights: BlendingSourceWeights = Field(default_factory=BlendingSourceWeights)


class BlendedSourceSummary(IntentShelfSchema):
    """Metadata about one retrieval source used or skipped during blending."""

    source: str = Field(..., min_length=1)
    requested: bool
    used: bool
    requested_k: int | None = Field(default=None, ge=1)
    returned_count: int = Field(default=0, ge=0)
    weight: float = Field(..., ge=0.0)
    normalization_strategy: str | None = None
    retrieval_method: str | None = None
    score_label: str | None = None
    message: str | None = None
    skip_reason: str | None = None


class BlendedCandidate(IntentShelfSchema):
    """One product candidate in the unified Phase 7 blended pool."""

    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_type_name: str | None = None
    product_group_name: str | None = None
    colour_group_name: str | None = None
    department_name: str | None = None
    image_path: str | None = None
    has_image: bool = False
    blended_score: float = Field(..., ge=0.0)
    contributing_sources: list[str] = Field(default_factory=list)
    raw_source_scores: dict[str, float] = Field(default_factory=dict)
    normalized_source_scores: dict[str, float] = Field(default_factory=dict)
    weighted_source_scores: dict[str, float] = Field(default_factory=dict)
    source_rank_positions: dict[str, int] = Field(default_factory=dict)
    source_weights: dict[str, float] = Field(default_factory=dict)


class BlendedCandidatesResponse(IntentShelfSchema):
    """Response payload for POST /candidates/blend."""

    blended_k: int = Field(..., ge=1)
    returned_candidate_count: int = Field(default=0, ge=0)
    normalization_strategy: str = Field(..., min_length=1)
    dedup_key: str = Field(default="product_id", min_length=1)
    used_sources: list[str] = Field(default_factory=list)
    source_weights: dict[str, float] = Field(default_factory=dict)
    message: str | None = None
    source_summaries: list[BlendedSourceSummary] = Field(default_factory=list)
    results: list[BlendedCandidate] = Field(default_factory=list)


class RerankingFeatureWeights(IntentShelfSchema):
    """Explicit feature weights used by the Phase 8 heuristic reranker."""

    blended_score: float = Field(default=1.0, ge=0.0)
    search_signal: float = Field(default=0.45, ge=0.0)
    search_presence: float = Field(default=0.15, ge=0.0)
    session_signal: float = Field(default=0.5, ge=0.0)
    session_presence: float = Field(default=0.15, ge=0.0)
    content_signal: float = Field(default=0.2, ge=0.0)
    collaborative_signal: float = Field(default=0.15, ge=0.0)
    popularity_signal: float = Field(default=0.1, ge=0.0)
    multi_source_signal: float = Field(default=0.25, ge=0.0)
    exact_anchor_penalty: float = Field(default=0.5, ge=0.0)


class RerankingFeatureWeightOverrides(IntentShelfSchema):
    """Optional overrides for the default Phase 8 feature weights."""

    blended_score: float | None = Field(default=None, ge=0.0)
    search_signal: float | None = Field(default=None, ge=0.0)
    search_presence: float | None = Field(default=None, ge=0.0)
    session_signal: float | None = Field(default=None, ge=0.0)
    session_presence: float | None = Field(default=None, ge=0.0)
    content_signal: float | None = Field(default=None, ge=0.0)
    collaborative_signal: float | None = Field(default=None, ge=0.0)
    popularity_signal: float | None = Field(default=None, ge=0.0)
    multi_source_signal: float | None = Field(default=None, ge=0.0)
    exact_anchor_penalty: float | None = Field(default=None, ge=0.0)


class RerankingDiversityConfig(IntentShelfSchema):
    """Simple deterministic diversity controls for the first ranked positions."""

    enabled: bool = True
    apply_top_n: int = Field(default=12, ge=1, le=100)
    product_type_penalty: float = Field(default=0.3, ge=0.0)
    product_group_penalty: float = Field(default=0.12, ge=0.0)
    max_penalty: float = Field(default=0.9, ge=0.0)


class RerankingDiversityOverrides(IntentShelfSchema):
    """Optional overrides for the default Phase 8 diversity settings."""

    enabled: bool | None = None
    apply_top_n: int | None = Field(default=None, ge=1, le=100)
    product_type_penalty: float | None = Field(default=None, ge=0.0)
    product_group_penalty: float | None = Field(default=None, ge=0.0)
    max_penalty: float | None = Field(default=None, ge=0.0)


class RerankingConfig(IntentShelfSchema):
    """Complete effective configuration for the Phase 8 reranker."""

    feature_weights: RerankingFeatureWeights = Field(default_factory=RerankingFeatureWeights)
    diversity: RerankingDiversityConfig = Field(default_factory=RerankingDiversityConfig)


class RerankingConfigOverrides(IntentShelfSchema):
    """Optional request-time overrides for the reranking configuration."""

    feature_weights: RerankingFeatureWeightOverrides | None = None
    diversity: RerankingDiversityOverrides | None = None


class RankingStrategySummary(IntentShelfSchema):
    """Human-readable metadata for one available ranking strategy."""

    key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class RankingStrategyDefinition(RankingStrategySummary):
    """One inspectable ranking strategy config bundle."""

    config: RerankingConfig


class RankingStrategyResolution(IntentShelfSchema):
    """How the backend resolved the requested ranking strategy."""

    requested_key: str = Field(..., min_length=1)
    resolved_key: str = Field(..., min_length=1)
    used_fallback: bool = False
    strategy: RankingStrategySummary


class RankingStrategiesResponse(IntentShelfSchema):
    """Response payload for GET /ranking/strategies."""

    default_strategy_key: str = Field(..., min_length=1)
    strategies: list[RankingStrategyDefinition] = Field(default_factory=list)


class FeedRerankRequest(BlendedCandidatesRequest):
    """Request payload for POST /feed/rerank."""

    ranking_strategy: str = Field(default=RANKING_STRATEGY_DEFAULT, min_length=1)
    reranked_k: int | None = Field(default=None, ge=1, le=200)
    reranking_overrides: RerankingConfigOverrides | None = None


class RerankingFeatureSummary(IntentShelfSchema):
    """Compact per-candidate feature values used during Phase 8 reranking."""

    blended_score: float = Field(..., ge=0.0)
    search_signal: float = Field(..., ge=0.0)
    search_presence: float = Field(..., ge=0.0)
    session_signal: float = Field(..., ge=0.0)
    session_presence: float = Field(..., ge=0.0)
    content_signal: float = Field(..., ge=0.0)
    collaborative_signal: float = Field(..., ge=0.0)
    popularity_signal: float = Field(..., ge=0.0)
    multi_source_signal: float = Field(..., ge=0.0)
    exact_anchor_penalty: float = Field(..., ge=0.0)
    diversity_penalty: float = Field(..., ge=0.0)
    source_count: int = Field(..., ge=0)
    repeated_product_type_count: int = Field(..., ge=0)
    repeated_product_group_count: int = Field(..., ge=0)


class RerankingScoreBreakdown(IntentShelfSchema):
    """Weighted contribution summary for one reranked candidate."""

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
    diversity_penalty_component: float


class RerankedCandidate(BlendedCandidate):
    """One final candidate returned by the Phase 8 reranker."""

    ranking_position: int = Field(..., ge=1)
    reranked_score: float
    base_reranking_score: float
    ranking_strategy: str = Field(..., min_length=1)
    reranking_features: RerankingFeatureSummary
    score_breakdown: RerankingScoreBreakdown


class FeedRerankResponse(IntentShelfSchema):
    """Response payload for POST /feed/rerank."""

    request_id: str | None = None
    ranking_strategy: str = Field(..., min_length=1)
    requested_ranking_strategy: str = Field(..., min_length=1)
    strategy_resolution: RankingStrategyResolution
    reranked_k: int = Field(..., ge=1)
    blended_candidate_count: int = Field(default=0, ge=0)
    returned_candidate_count: int = Field(default=0, ge=0)
    normalization_strategy: str = Field(..., min_length=1)
    dedup_key: str = Field(default="product_id", min_length=1)
    used_sources: list[str] = Field(default_factory=list)
    source_weights: dict[str, float] = Field(default_factory=dict)
    effective_reranking_config: RerankingConfig
    message: str | None = None
    source_summaries: list[BlendedSourceSummary] = Field(default_factory=list)
    results: list[RerankedCandidate] = Field(default_factory=list)


class FeedExplanationOptions(IntentShelfSchema):
    """Small request-time knobs for Phase 9 explanation output."""

    include_evidence: bool = True
    max_supporting_reasons: int = Field(default=2, ge=0, le=5)


class FeedExplainRequest(FeedRerankRequest):
    """Request payload for POST /feed/explain."""

    explanation_options: FeedExplanationOptions = Field(
        default_factory=FeedExplanationOptions
    )


class CandidateExplanationEvidence(IntentShelfSchema):
    """Compact machine-readable evidence behind one explanation choice."""

    rule_name: str = Field(..., min_length=1)
    dominant_source: str | None = None
    dominant_raw_score: float | None = None
    dominant_normalized_score: float | None = None
    dominant_weighted_score: float | None = None
    contributing_sources: list[str] = Field(default_factory=list)
    meaningful_sources: list[str] = Field(default_factory=list)
    query_present: bool = False
    query_text: str | None = None
    normalized_query: str | None = None
    session_context_used: bool = False
    session_signal_count: int = Field(default=0, ge=0)
    anchor_product_used: bool = False
    anchor_product_id: str | None = None
    collaborative_is_popularity: bool = False
    source_count: int = Field(default=0, ge=0)
    multi_source_signal: float = Field(default=0.0, ge=0.0)
    diversity_penalty: float = Field(default=0.0, ge=0.0)


class CandidateExplanation(IntentShelfSchema):
    """Primary and supporting deterministic explanation text for one candidate."""

    short_reason: str = Field(..., min_length=1)
    supporting_reasons: list[str] = Field(default_factory=list)
    reason_tags: list[str] = Field(default_factory=list)
    explanation_source: str = Field(..., min_length=1)
    evidence: CandidateExplanationEvidence | None = None


class ExplainedRerankedCandidate(RerankedCandidate):
    """One final reranked candidate plus Phase 9 explanation metadata."""

    explanation: CandidateExplanation


class FeedExplainResponse(FeedRerankResponse):
    """Response payload for POST /feed/explain."""

    explanation_mode: Literal["deterministic_rule_based"] = (
        "deterministic_rule_based"
    )
    explanation_options: FeedExplanationOptions
    results: list[ExplainedRerankedCandidate] = Field(default_factory=list)
