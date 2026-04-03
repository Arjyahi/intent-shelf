from fastapi import APIRouter, HTTPException, Query

from app.schemas.retrieval import SimilarProductsResponse
from app.services.content_retrieval import get_content_retrieval_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{product_id}/similar", response_model=SimilarProductsResponse)
def get_similar_products(
    product_id: str,
    k: int = Query(default=12, ge=1, le=100),
) -> SimilarProductsResponse:
    try:
        service = get_content_retrieval_service()
        return service.get_similar_products(product_id=product_id, k=k)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
