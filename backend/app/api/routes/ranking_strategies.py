from fastapi import APIRouter

from app.schemas.retrieval import RankingStrategiesResponse
from app.services.ranking_strategies import get_ranking_strategy_registry

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("/strategies", response_model=RankingStrategiesResponse)
def list_ranking_strategies() -> RankingStrategiesResponse:
    registry = get_ranking_strategy_registry()
    return registry.build_response()
