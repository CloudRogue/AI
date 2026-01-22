from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = "ok"


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse()
# app/main.py (또는 create_app() 안)
from fastapi import FastAPI
from app.routes.health import router as health_router

app = FastAPI()

app.include_router(health_router, prefix="/api")