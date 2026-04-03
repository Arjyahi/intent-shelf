from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}
