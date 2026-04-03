from fastapi import APIRouter

from app.schemas.retrieval import BlendedCandidatesRequest, BlendedCandidatesResponse
from app.services.candidate_blending import get_candidate_blending_service

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/blend", response_model=BlendedCandidatesResponse)
def blend_candidates(
    request: BlendedCandidatesRequest,
) -> BlendedCandidatesResponse:
    service = get_candidate_blending_service()
    return service.blend_candidates(request=request)
