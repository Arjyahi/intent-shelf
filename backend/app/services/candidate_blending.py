from dataclasses import dataclass, field
from functools import lru_cache

from app.schemas.retrieval import (
    BlendedCandidate,
    BlendedCandidatesRequest,
    BlendedCandidatesResponse,
    BlendedSourceSummary,
    SessionRecommendationsRequest,
)
from app.services.collaborative_retrieval import (
    CollaborativeRetrievalService,
    get_collaborative_retrieval_service,
)
from app.services.content_retrieval import ContentRetrievalService, get_content_retrieval_service
from app.services.search_retrieval import SearchRetrievalService, get_search_retrieval_service
from app.services.session_retrieval import SessionRetrievalService, get_session_retrieval_service

SOURCE_COLLABORATIVE = "collaborative"
SOURCE_CONTENT = "content"
SOURCE_SEARCH = "search"
SOURCE_SESSION = "session"

SOURCE_ORDER = [
    SOURCE_COLLABORATIVE,
    SOURCE_CONTENT,
    SOURCE_SEARCH,
    SOURCE_SESSION,
]

CONTENT_RETRIEVAL_METHOD = "multimodal_faiss_nearest_neighbors"
CONTENT_SCORE_LABEL = "faiss_inner_product"


@dataclass(frozen=True)
class SourceCandidate:
    product_id: str
    product_name: str
    product_type_name: str | None
    product_group_name: str | None
    colour_group_name: str | None
    department_name: str | None
    image_path: str | None
    has_image: bool
    raw_score: float


@dataclass
class CandidateAccumulator:
    product_id: str
    product_name: str
    product_type_name: str | None = None
    product_group_name: str | None = None
    colour_group_name: str | None = None
    department_name: str | None = None
    image_path: str | None = None
    has_image: bool = False
    contributing_sources: list[str] = field(default_factory=list)
    raw_source_scores: dict[str, float] = field(default_factory=dict)
    normalized_source_scores: dict[str, float] = field(default_factory=dict)
    weighted_source_scores: dict[str, float] = field(default_factory=dict)
    source_rank_positions: dict[str, int] = field(default_factory=dict)
    source_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class SourceCollection:
    source: str
    requested: bool
    used: bool
    requested_k: int | None
    weight: float
    candidates: list[SourceCandidate] = field(default_factory=list)
    normalization_strategy: str | None = None
    retrieval_method: str | None = None
    score_label: str | None = None
    message: str | None = None
    skip_reason: str | None = None

    def to_summary(self) -> BlendedSourceSummary:
        return BlendedSourceSummary(
            source=self.source,
            requested=self.requested,
            used=self.used,
            requested_k=self.requested_k,
            returned_count=len(self.candidates),
            weight=self.weight,
            normalization_strategy=self.normalization_strategy,
            retrieval_method=self.retrieval_method,
            score_label=self.score_label,
            message=self.message,
            skip_reason=self.skip_reason,
        )


def _build_source_candidate(item: object) -> SourceCandidate:
    return SourceCandidate(
        product_id=str(getattr(item, "product_id")),
        product_name=str(getattr(item, "product_name")),
        product_type_name=getattr(item, "product_type_name", None),
        product_group_name=getattr(item, "product_group_name", None),
        colour_group_name=getattr(item, "colour_group_name", None),
        department_name=getattr(item, "department_name", None),
        image_path=getattr(item, "image_path", None),
        has_image=bool(getattr(item, "has_image", False)),
        raw_score=float(getattr(item, "score")),
    )


def _prefer_existing_value(current_value: str | None, new_value: str | None) -> str | None:
    if current_value not in (None, ""):
        return current_value
    return new_value


class CandidateBlendingService:
    """
    Phase 7 candidate blending service.

    This layer does not do final ranking. It only collects source candidates,
    normalizes scores within each source list, deduplicates by product_id, and
    computes a simple weighted blended score for later reranking.
    """

    def __init__(
        self,
        collaborative_service: CollaborativeRetrievalService | None = None,
        content_service: ContentRetrievalService | None = None,
        search_service: SearchRetrievalService | None = None,
        session_service: SessionRetrievalService | None = None,
    ) -> None:
        self.collaborative_service = collaborative_service or get_collaborative_retrieval_service()
        self.content_service = content_service or get_content_retrieval_service()
        self.search_service = search_service or get_search_retrieval_service()
        self.session_service = session_service or get_session_retrieval_service()

    def blend_candidates(
        self,
        request: BlendedCandidatesRequest,
    ) -> BlendedCandidatesResponse:
        source_weights = request.source_weights.model_dump()
        source_collections = [
            self._collect_collaborative_candidates(request=request, weight=source_weights[SOURCE_COLLABORATIVE]),
            self._collect_content_candidates(request=request, weight=source_weights[SOURCE_CONTENT]),
            self._collect_search_candidates(request=request, weight=source_weights[SOURCE_SEARCH]),
            self._collect_session_candidates(request=request, weight=source_weights[SOURCE_SESSION]),
        ]

        merged_candidates = self._merge_source_candidates(
            source_collections=source_collections,
            normalization_strategy=request.normalization_strategy,
        )
        ranked_candidates = self._rank_blended_candidates(merged_candidates)
        final_candidates = ranked_candidates[: request.blended_k]

        used_sources = [
            source_collection.source
            for source_collection in source_collections
            if source_collection.used
        ]
        message = self._build_response_message(
            source_collections=source_collections,
            final_candidates=final_candidates,
        )

        return BlendedCandidatesResponse(
            blended_k=request.blended_k,
            returned_candidate_count=len(final_candidates),
            normalization_strategy=request.normalization_strategy,
            dedup_key="product_id",
            used_sources=used_sources,
            source_weights=source_weights,
            message=message,
            source_summaries=[collection.to_summary() for collection in source_collections],
            results=final_candidates,
        )

    def _collect_collaborative_candidates(
        self,
        request: BlendedCandidatesRequest,
        weight: float,
    ) -> SourceCollection:
        if not request.user_id:
            return SourceCollection(
                source=SOURCE_COLLABORATIVE,
                requested=False,
                used=False,
                requested_k=None,
                weight=weight,
                skip_reason="Skipped because user_id was not provided.",
            )

        try:
            response = self.collaborative_service.get_recommendations(
                user_id=request.user_id,
                k=request.collaborative_k,
                exclude_seen_items=request.exclude_seen_items,
            )
        except (FileNotFoundError, ImportError, ValueError) as exc:
            return SourceCollection(
                source=SOURCE_COLLABORATIVE,
                requested=True,
                used=False,
                requested_k=request.collaborative_k,
                weight=weight,
                skip_reason=str(exc),
            )

        return SourceCollection(
            source=SOURCE_COLLABORATIVE,
            requested=True,
            used=True,
            requested_k=request.collaborative_k,
            weight=weight,
            candidates=[_build_source_candidate(item) for item in response.results],
            normalization_strategy=request.normalization_strategy,
            retrieval_method=str(response.model_name or "implicit_bpr_recommendation"),
            score_label=response.score_source,
            message=response.message,
        )

    def _collect_content_candidates(
        self,
        request: BlendedCandidatesRequest,
        weight: float,
    ) -> SourceCollection:
        if not request.anchor_product_id:
            return SourceCollection(
                source=SOURCE_CONTENT,
                requested=False,
                used=False,
                requested_k=None,
                weight=weight,
                skip_reason="Skipped because anchor_product_id was not provided.",
            )

        try:
            response = self.content_service.get_similar_products(
                product_id=request.anchor_product_id,
                k=request.content_k,
            )
        except KeyError as exc:
            return SourceCollection(
                source=SOURCE_CONTENT,
                requested=True,
                used=False,
                requested_k=request.content_k,
                weight=weight,
                skip_reason=exc.args[0],
            )
        except (FileNotFoundError, ValueError) as exc:
            return SourceCollection(
                source=SOURCE_CONTENT,
                requested=True,
                used=False,
                requested_k=request.content_k,
                weight=weight,
                skip_reason=str(exc),
            )

        return SourceCollection(
            source=SOURCE_CONTENT,
            requested=True,
            used=True,
            requested_k=request.content_k,
            weight=weight,
            candidates=[_build_source_candidate(item) for item in response.results],
            normalization_strategy=request.normalization_strategy,
            retrieval_method=CONTENT_RETRIEVAL_METHOD,
            score_label=CONTENT_SCORE_LABEL,
            message=None,
        )

    def _collect_search_candidates(
        self,
        request: BlendedCandidatesRequest,
        weight: float,
    ) -> SourceCollection:
        if not request.query:
            return SourceCollection(
                source=SOURCE_SEARCH,
                requested=False,
                used=False,
                requested_k=None,
                weight=weight,
                skip_reason="Skipped because query was not provided.",
            )

        try:
            response = self.search_service.search(query=request.query, k=request.search_k)
        except (FileNotFoundError, ValueError) as exc:
            return SourceCollection(
                source=SOURCE_SEARCH,
                requested=True,
                used=False,
                requested_k=request.search_k,
                weight=weight,
                skip_reason=str(exc),
            )

        return SourceCollection(
            source=SOURCE_SEARCH,
            requested=True,
            used=True,
            requested_k=request.search_k,
            weight=weight,
            candidates=[_build_source_candidate(item) for item in response.results],
            normalization_strategy=request.normalization_strategy,
            retrieval_method=response.retrieval_method,
            score_label=response.scoring_method,
            message=response.message,
        )

    def _collect_session_candidates(
        self,
        request: BlendedCandidatesRequest,
        weight: float,
    ) -> SourceCollection:
        if not self._has_session_context(request):
            return SourceCollection(
                source=SOURCE_SESSION,
                requested=False,
                used=False,
                requested_k=None,
                weight=weight,
                skip_reason=(
                    "Skipped because no session_events, like_events, or save_events were provided."
                ),
            )

        session_request = SessionRecommendationsRequest(
            session=request.session,
            session_events=request.session_events,
            like_events=request.like_events,
            save_events=request.save_events,
            k=request.session_k,
            max_recent_events=request.max_recent_events,
            exclude_recent_products=request.exclude_recent_products,
        )

        try:
            response = self.session_service.get_recommendations(request=session_request)
        except (FileNotFoundError, ValueError) as exc:
            return SourceCollection(
                source=SOURCE_SESSION,
                requested=True,
                used=False,
                requested_k=request.session_k,
                weight=weight,
                skip_reason=str(exc),
            )

        return SourceCollection(
            source=SOURCE_SESSION,
            requested=True,
            used=True,
            requested_k=request.session_k,
            weight=weight,
            candidates=[_build_source_candidate(item) for item in response.results],
            normalization_strategy=request.normalization_strategy,
            retrieval_method=response.retrieval_method,
            score_label=response.score_source,
            message=response.message,
        )

    @staticmethod
    def _has_session_context(request: BlendedCandidatesRequest) -> bool:
        return bool(request.session_events or request.like_events or request.save_events)

    def _merge_source_candidates(
        self,
        source_collections: list[SourceCollection],
        normalization_strategy: str,
    ) -> dict[str, CandidateAccumulator]:
        merged_candidates: dict[str, CandidateAccumulator] = {}

        for source_collection in source_collections:
            if not source_collection.used or not source_collection.candidates:
                continue

            normalized_scores = self._normalize_source_scores(
                candidates=source_collection.candidates,
                normalization_strategy=normalization_strategy,
            )

            for rank_position, (candidate, normalized_score) in enumerate(
                zip(source_collection.candidates, normalized_scores),
                start=1,
            ):
                merged_candidate = merged_candidates.get(candidate.product_id)
                if merged_candidate is None:
                    merged_candidate = CandidateAccumulator(
                        product_id=candidate.product_id,
                        product_name=candidate.product_name,
                        product_type_name=candidate.product_type_name,
                        product_group_name=candidate.product_group_name,
                        colour_group_name=candidate.colour_group_name,
                        department_name=candidate.department_name,
                        image_path=candidate.image_path,
                        has_image=candidate.has_image,
                    )
                    merged_candidates[candidate.product_id] = merged_candidate
                else:
                    merged_candidate.product_name = _prefer_existing_value(
                        merged_candidate.product_name,
                        candidate.product_name,
                    ) or candidate.product_name
                    merged_candidate.product_type_name = _prefer_existing_value(
                        merged_candidate.product_type_name,
                        candidate.product_type_name,
                    )
                    merged_candidate.product_group_name = _prefer_existing_value(
                        merged_candidate.product_group_name,
                        candidate.product_group_name,
                    )
                    merged_candidate.colour_group_name = _prefer_existing_value(
                        merged_candidate.colour_group_name,
                        candidate.colour_group_name,
                    )
                    merged_candidate.department_name = _prefer_existing_value(
                        merged_candidate.department_name,
                        candidate.department_name,
                    )
                    merged_candidate.image_path = _prefer_existing_value(
                        merged_candidate.image_path,
                        candidate.image_path,
                    )
                    merged_candidate.has_image = merged_candidate.has_image or candidate.has_image

                if source_collection.source not in merged_candidate.contributing_sources:
                    merged_candidate.contributing_sources.append(source_collection.source)

                merged_candidate.raw_source_scores[source_collection.source] = candidate.raw_score
                merged_candidate.normalized_source_scores[source_collection.source] = normalized_score
                merged_candidate.weighted_source_scores[source_collection.source] = (
                    normalized_score * source_collection.weight
                )
                merged_candidate.source_rank_positions[source_collection.source] = rank_position
                merged_candidate.source_weights[source_collection.source] = source_collection.weight

        return merged_candidates

    @staticmethod
    def _normalize_source_scores(
        candidates: list[SourceCandidate],
        normalization_strategy: str,
    ) -> list[float]:
        if normalization_strategy != "min_max":
            raise ValueError(f"Unsupported normalization strategy: {normalization_strategy}")

        if not candidates:
            return []

        raw_scores = [candidate.raw_score for candidate in candidates]
        min_score = min(raw_scores)
        max_score = max(raw_scores)

        if max_score == min_score:
            return [1.0 for _ in raw_scores]

        return [
            (raw_score - min_score) / (max_score - min_score)
            for raw_score in raw_scores
        ]

    @staticmethod
    def _rank_blended_candidates(
        merged_candidates: dict[str, CandidateAccumulator],
    ) -> list[BlendedCandidate]:
        blended_candidates = [
            BlendedCandidate(
                product_id=candidate.product_id,
                product_name=candidate.product_name,
                product_type_name=candidate.product_type_name,
                product_group_name=candidate.product_group_name,
                colour_group_name=candidate.colour_group_name,
                department_name=candidate.department_name,
                image_path=candidate.image_path,
                has_image=candidate.has_image,
                blended_score=sum(candidate.weighted_source_scores.values()),
                contributing_sources=candidate.contributing_sources,
                raw_source_scores=candidate.raw_source_scores,
                normalized_source_scores=candidate.normalized_source_scores,
                weighted_source_scores=candidate.weighted_source_scores,
                source_rank_positions=candidate.source_rank_positions,
                source_weights=candidate.source_weights,
            )
            for candidate in merged_candidates.values()
        ]

        return sorted(
            blended_candidates,
            key=lambda candidate: (
                -candidate.blended_score,
                -len(candidate.contributing_sources),
                min(candidate.source_rank_positions.values(), default=10_000),
                candidate.product_id,
            ),
        )

    @staticmethod
    def _build_response_message(
        source_collections: list[SourceCollection],
        final_candidates: list[BlendedCandidate],
    ) -> str | None:
        requested_sources = [
            source_collection
            for source_collection in source_collections
            if source_collection.requested
        ]
        used_sources = [
            source_collection
            for source_collection in source_collections
            if source_collection.used
        ]

        if not requested_sources:
            return (
                "No candidate sources were requested. Provide at least one of user_id, "
                "query, anchor_product_id, or session events."
            )

        if not used_sources:
            return "No candidate sources were usable for this request."

        if not final_candidates:
            return "Candidate sources were used, but no blended candidates were produced."

        return None


@lru_cache(maxsize=1)
def get_candidate_blending_service() -> CandidateBlendingService:
    return CandidateBlendingService()
