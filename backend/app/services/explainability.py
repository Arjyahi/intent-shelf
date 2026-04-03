from dataclasses import dataclass
from functools import lru_cache

from app.schemas.retrieval import (
    BlendedSourceSummary,
    CandidateExplanation,
    CandidateExplanationEvidence,
    ExplainedRerankedCandidate,
    FeedExplainRequest,
    FeedExplainResponse,
    FeedExplanationOptions,
    FeedRerankRequest,
    RerankedCandidate,
)
from app.services.reranking import FeedRerankingService, get_feed_reranking_service

SOURCE_SEARCH = "search"
SOURCE_SESSION = "session"
SOURCE_CONTENT = "content"
SOURCE_COLLABORATIVE = "collaborative"
SOURCE_POPULARITY = "popularity"
SOURCE_MULTI_SIGNAL = "multi_signal"
SOURCE_FALLBACK = "fallback"

SOURCE_PRIORITY = [
    SOURCE_SEARCH,
    SOURCE_SESSION,
    SOURCE_CONTENT,
    SOURCE_COLLABORATIVE,
]

RECENT_VIEW_EVENT_TYPES = {
    "product_view",
    "detail_open",
    "similar_item_click",
}

# These thresholds intentionally stay simple and visible. They only decide when a
# source is strong enough to drive explanation text; they do not change ranking.
MIN_PRIMARY_SOURCE_WEIGHTED_SCORE = 0.15
MIN_SUPPORTING_SOURCE_WEIGHTED_SCORE = 0.1


@dataclass(frozen=True)
class ExplanationDecision:
    rule_name: str
    short_reason: str
    reason_tags: list[str]
    explanation_source: str


@dataclass(frozen=True)
class ExplanationContext:
    request: FeedExplainRequest
    normalized_query: str | None
    session_context_used: bool
    session_signal_count: int
    has_recent_product_views: bool
    collaborative_is_popularity: bool


class FeedExplainabilityService:
    """
    Phase 9 explanation generator.

    This service does not rerank items on its own. It wraps the Phase 8
    reranking service, reads the metadata that already exists, and converts it
    into compact rule-based explanation text plus small evidence objects.
    """

    def __init__(
        self,
        reranking_service: FeedRerankingService | None = None,
    ) -> None:
        self.reranking_service = reranking_service or get_feed_reranking_service()

    def explain_feed(
        self,
        request: FeedExplainRequest,
    ) -> FeedExplainResponse:
        rerank_request = FeedRerankRequest.model_validate(
            request.model_dump(exclude={"explanation_options"})
        )
        rerank_response = self.reranking_service.rerank_feed(request=rerank_request)
        context = self._build_context(
            request=request,
            source_summaries=rerank_response.source_summaries,
        )

        explained_results = [
            self._build_explained_candidate(
                candidate=candidate,
                context=context,
                options=request.explanation_options,
            )
            for candidate in rerank_response.results
        ]

        response_payload = rerank_response.model_dump(exclude={"results"})
        return FeedExplainResponse(
            **response_payload,
            explanation_mode="deterministic_rule_based",
            explanation_options=request.explanation_options,
            results=explained_results,
        )

    @staticmethod
    def _build_context(
        request: FeedExplainRequest,
        source_summaries: list[BlendedSourceSummary],
    ) -> ExplanationContext:
        normalized_query = FeedExplainabilityService._normalize_query(request.query)
        session_context_used = bool(
            request.session_events or request.like_events or request.save_events
        )
        session_signal_count = (
            len(request.session_events)
            + len(request.like_events)
            + len(request.save_events)
        )
        has_recent_product_views = any(
            event.product_id and event.event_type in RECENT_VIEW_EVENT_TYPES
            for event in request.session_events
        )
        collaborative_summary = FeedExplainabilityService._get_source_summary(
            source_summaries=source_summaries,
            source=SOURCE_COLLABORATIVE,
        )
        collaborative_is_popularity = (
            collaborative_summary is not None
            and collaborative_summary.score_label == "global_popularity"
        )
        return ExplanationContext(
            request=request,
            normalized_query=normalized_query,
            session_context_used=session_context_used,
            session_signal_count=session_signal_count,
            has_recent_product_views=has_recent_product_views,
            collaborative_is_popularity=collaborative_is_popularity,
        )

    def _build_explained_candidate(
        self,
        candidate: RerankedCandidate,
        context: ExplanationContext,
        options: FeedExplanationOptions,
    ) -> ExplainedRerankedCandidate:
        primary_decision = self._choose_primary_decision(
            candidate=candidate,
            context=context,
        )
        supporting_reasons, supporting_tags = self._build_supporting_reasons(
            candidate=candidate,
            context=context,
            primary_decision=primary_decision,
            max_reasons=options.max_supporting_reasons,
        )

        evidence = None
        if options.include_evidence:
            evidence = self._build_evidence(
                candidate=candidate,
                context=context,
                primary_decision=primary_decision,
            )

        explanation = CandidateExplanation(
            short_reason=primary_decision.short_reason,
            supporting_reasons=supporting_reasons,
            reason_tags=self._unique_in_order(
                [*primary_decision.reason_tags, *supporting_tags]
            ),
            explanation_source=primary_decision.explanation_source,
            evidence=evidence,
        )
        candidate_payload = candidate.model_dump(exclude={"explanation"})
        return ExplainedRerankedCandidate(
            **candidate_payload,
            explanation=explanation,
        )

    def _choose_primary_decision(
        self,
        candidate: RerankedCandidate,
        context: ExplanationContext,
    ) -> ExplanationDecision:
        dominant_source = self._get_dominant_source(candidate)
        dominant_weighted_score = candidate.weighted_source_scores.get(dominant_source, 0.0)
        meaningful_sources = self._get_meaningful_sources(candidate)

        if (
            context.normalized_query
            and dominant_source == SOURCE_SEARCH
            and dominant_weighted_score >= MIN_PRIMARY_SOURCE_WEIGHTED_SCORE
        ):
            return ExplanationDecision(
                rule_name="search_dominant",
                short_reason=f'Because you searched for "{context.normalized_query}"',
                reason_tags=["search_match"],
                explanation_source=SOURCE_SEARCH,
            )

        if (
            context.session_context_used
            and dominant_source == SOURCE_SESSION
            and dominant_weighted_score >= MIN_PRIMARY_SOURCE_WEIGHTED_SCORE
        ):
            return ExplanationDecision(
                rule_name="session_dominant",
                short_reason=self._build_session_reason_text(context),
                reason_tags=self._build_session_reason_tags(context),
                explanation_source=SOURCE_SESSION,
            )

        if (
            context.request.anchor_product_id
            and candidate.product_id != context.request.anchor_product_id
            and dominant_source == SOURCE_CONTENT
            and dominant_weighted_score >= MIN_PRIMARY_SOURCE_WEIGHTED_SCORE
        ):
            return ExplanationDecision(
                rule_name="content_anchor_dominant",
                short_reason="Similar to the product you opened",
                reason_tags=["anchor_similarity", "content_signal"],
                explanation_source=SOURCE_CONTENT,
            )

        if (
            dominant_source == SOURCE_COLLABORATIVE
            and dominant_weighted_score >= MIN_PRIMARY_SOURCE_WEIGHTED_SCORE
        ):
            if context.collaborative_is_popularity:
                return ExplanationDecision(
                    rule_name="popularity_dominant",
                    short_reason="Popular with many shoppers overall",
                    reason_tags=["popularity_signal"],
                    explanation_source=SOURCE_POPULARITY,
                )
            return ExplanationDecision(
                rule_name="collaborative_dominant",
                short_reason="Popular among users with similar purchase history",
                reason_tags=["collaborative_signal"],
                explanation_source=SOURCE_COLLABORATIVE,
            )

        if len(meaningful_sources) >= 2:
            return ExplanationDecision(
                rule_name=self._build_multi_signal_rule_name(context, meaningful_sources),
                short_reason=self._build_multi_signal_reason_text(context, meaningful_sources),
                reason_tags=self._build_multi_signal_reason_tags(
                    context=context,
                    meaningful_sources=meaningful_sources,
                ),
                explanation_source=SOURCE_MULTI_SIGNAL,
            )

        fallback_sources = meaningful_sources or self._get_ranked_sources(candidate)
        return ExplanationDecision(
            rule_name="fallback",
            short_reason=self._build_fallback_reason_text(
                context=context,
                sources=fallback_sources,
            ),
            reason_tags=["fallback"],
            explanation_source=SOURCE_FALLBACK,
        )

    def _build_supporting_reasons(
        self,
        candidate: RerankedCandidate,
        context: ExplanationContext,
        primary_decision: ExplanationDecision,
        max_reasons: int,
    ) -> tuple[list[str], list[str]]:
        if max_reasons <= 0:
            return [], []

        meaningful_sources = self._get_meaningful_sources(candidate)
        supporting_reasons: list[str] = []
        supporting_tags: list[str] = []

        def add_reason(reason: str, tags: list[str]) -> None:
            if len(supporting_reasons) >= max_reasons:
                return
            if reason == primary_decision.short_reason or reason in supporting_reasons:
                return
            supporting_reasons.append(reason)
            supporting_tags.extend(tags)

        if (
            context.normalized_query
            and SOURCE_SEARCH in meaningful_sources
            and primary_decision.explanation_source != SOURCE_SEARCH
        ):
            add_reason(
                f'Because you searched for "{context.normalized_query}"',
                ["search_match"],
            )

        if (
            context.session_context_used
            and SOURCE_SESSION in meaningful_sources
            and primary_decision.explanation_source != SOURCE_SESSION
        ):
            add_reason(
                self._build_session_reason_text(context),
                self._build_session_reason_tags(context),
            )

        if (
            context.request.anchor_product_id
            and candidate.product_id != context.request.anchor_product_id
            and SOURCE_CONTENT in meaningful_sources
            and primary_decision.explanation_source != SOURCE_CONTENT
        ):
            add_reason(
                "Similar to the product you opened",
                ["anchor_similarity", "content_signal"],
            )

        if (
            SOURCE_COLLABORATIVE in meaningful_sources
            and primary_decision.explanation_source
            not in {SOURCE_COLLABORATIVE, SOURCE_POPULARITY}
        ):
            add_reason(
                self._build_collaborative_reason_text(context),
                self._build_collaborative_reason_tags(context),
            )

        if (
            len(meaningful_sources) >= 2
            and primary_decision.explanation_source != SOURCE_MULTI_SIGNAL
        ):
            add_reason(
                self._build_multi_signal_reason_text(context, meaningful_sources),
                self._build_multi_signal_reason_tags(
                    context=context,
                    meaningful_sources=meaningful_sources,
                ),
            )

        if (
            self._should_add_diversity_support_reason(candidate)
            and primary_decision.explanation_source != "diversity"
        ):
            add_reason(
                "Chosen to keep the top of the feed more varied",
                ["diversity_strategy"],
            )

        return supporting_reasons, self._unique_in_order(supporting_tags)

    def _build_evidence(
        self,
        candidate: RerankedCandidate,
        context: ExplanationContext,
        primary_decision: ExplanationDecision,
    ) -> CandidateExplanationEvidence:
        dominant_source = self._get_dominant_source(candidate)
        meaningful_sources = self._get_meaningful_sources(candidate)
        return CandidateExplanationEvidence(
            rule_name=primary_decision.rule_name,
            dominant_source=dominant_source,
            dominant_raw_score=candidate.raw_source_scores.get(dominant_source),
            dominant_normalized_score=candidate.normalized_source_scores.get(dominant_source),
            dominant_weighted_score=candidate.weighted_source_scores.get(dominant_source),
            contributing_sources=candidate.contributing_sources,
            meaningful_sources=meaningful_sources,
            query_present=bool(context.normalized_query),
            query_text=context.request.query,
            normalized_query=context.normalized_query,
            session_context_used=context.session_context_used,
            session_signal_count=context.session_signal_count,
            anchor_product_used=bool(context.request.anchor_product_id),
            anchor_product_id=context.request.anchor_product_id,
            collaborative_is_popularity=context.collaborative_is_popularity,
            source_count=candidate.reranking_features.source_count,
            multi_source_signal=candidate.reranking_features.multi_source_signal,
            diversity_penalty=candidate.reranking_features.diversity_penalty,
        )

    @staticmethod
    def _normalize_query(query: str | None) -> str | None:
        if query is None:
            return None
        normalized_query = " ".join(query.split())
        return normalized_query or None

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
    def _source_order_key(source: str) -> tuple[int, str]:
        if source in SOURCE_PRIORITY:
            return SOURCE_PRIORITY.index(source), source
        return len(SOURCE_PRIORITY), source

    def _get_ranked_sources(self, candidate: RerankedCandidate) -> list[str]:
        ordered_scores = sorted(
            candidate.weighted_source_scores.items(),
            key=lambda item: (
                -item[1],
                -candidate.normalized_source_scores.get(item[0], 0.0),
                self._source_order_key(item[0]),
            ),
        )
        if ordered_scores:
            return [source for source, _score in ordered_scores]
        return sorted(candidate.contributing_sources, key=self._source_order_key)

    def _get_dominant_source(self, candidate: RerankedCandidate) -> str | None:
        ranked_sources = self._get_ranked_sources(candidate)
        if not ranked_sources:
            return None
        return ranked_sources[0]

    def _get_meaningful_sources(self, candidate: RerankedCandidate) -> list[str]:
        return [
            source
            for source in self._get_ranked_sources(candidate)
            if candidate.weighted_source_scores.get(source, 0.0)
            >= MIN_SUPPORTING_SOURCE_WEIGHTED_SCORE
        ]

    @staticmethod
    def _build_session_reason_text(context: ExplanationContext) -> str:
        if context.has_recent_product_views:
            return "Similar to items you recently viewed"
        return "Boosted by your current session activity"

    @staticmethod
    def _build_session_reason_tags(context: ExplanationContext) -> list[str]:
        if context.has_recent_product_views:
            return ["session_signal", "recent_views"]
        return ["session_signal"]

    @staticmethod
    def _build_collaborative_reason_text(context: ExplanationContext) -> str:
        if context.collaborative_is_popularity:
            return "Popular with many shoppers overall"
        return "Popular among users with similar purchase history"

    @staticmethod
    def _build_collaborative_reason_tags(context: ExplanationContext) -> list[str]:
        if context.collaborative_is_popularity:
            return ["popularity_signal"]
        return ["collaborative_signal"]

    @staticmethod
    def _build_multi_signal_rule_name(
        context: ExplanationContext,
        meaningful_sources: list[str],
    ) -> str:
        if (
            context.normalized_query
            and context.session_context_used
            and SOURCE_SEARCH in meaningful_sources
            and SOURCE_SESSION in meaningful_sources
        ):
            return "shopping_intent_multi_signal"
        return "multi_signal_support"

    @staticmethod
    def _build_multi_signal_reason_text(
        context: ExplanationContext,
        meaningful_sources: list[str],
    ) -> str:
        if (
            context.normalized_query
            and context.session_context_used
            and SOURCE_SEARCH in meaningful_sources
            and SOURCE_SESSION in meaningful_sources
        ):
            return "Matches your recent shopping intent"
        return "Recommended from multiple matching signals"

    @staticmethod
    def _build_multi_signal_reason_tags(
        context: ExplanationContext,
        meaningful_sources: list[str],
    ) -> list[str]:
        if (
            context.normalized_query
            and context.session_context_used
            and SOURCE_SEARCH in meaningful_sources
            and SOURCE_SESSION in meaningful_sources
        ):
            return ["multi_signal", "search_match", "session_signal", "shopping_intent"]
        return ["multi_signal"]

    def _build_fallback_reason_text(
        self,
        context: ExplanationContext,
        sources: list[str],
    ) -> str:
        source_labels = [
            self._build_friendly_source_label(context=context, source=source)
            for source in sources
        ]
        joined_labels = self._join_labels(source_labels)
        return f"Recommended using {joined_labels}"

    @staticmethod
    def _build_friendly_source_label(
        context: ExplanationContext,
        source: str,
    ) -> str:
        if source == SOURCE_SEARCH:
            return "your search signals" if context.normalized_query else "search signals"
        if source == SOURCE_SESSION:
            return "your recent activity"
        if source == SOURCE_CONTENT:
            return "similar-item matching"
        if source == SOURCE_COLLABORATIVE:
            if context.collaborative_is_popularity:
                return "overall shopper popularity"
            return "similar shopper behavior"
        return source

    @staticmethod
    def _join_labels(labels: list[str]) -> str:
        if not labels:
            return "the current feed signals"
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return f"{labels[0]} and {labels[1]}"
        return f"{', '.join(labels[:-1])}, and {labels[-1]}"

    @staticmethod
    def _should_add_diversity_support_reason(candidate: RerankedCandidate) -> bool:
        return (
            candidate.ranking_strategy == "diversity_boosted"
            and candidate.ranking_position > 1
            and candidate.reranking_features.diversity_penalty == 0.0
            and candidate.reranking_features.repeated_product_type_count == 0
            and candidate.reranking_features.repeated_product_group_count == 0
        )

    @staticmethod
    def _unique_in_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        return unique_values


@lru_cache(maxsize=1)
def get_feed_explainability_service() -> FeedExplainabilityService:
    return FeedExplainabilityService()
