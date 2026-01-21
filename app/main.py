from __future__ import annotations

from dotenv import load_dotenv

# ✅ 라우터 import 전에 env 먼저 로드
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.ingest import router as ingest_router
from app.routes.eligibility import router as eligibility_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="PDF Ingest AI Pipeline",
        version="1.0.0",
        description="LH/SH 공고 PDF → OpenAI → 온보딩 질문 초안 생성 파이프라인",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        ingest_router,
        prefix="/api",
        tags=["ingest"],
    )

    app.include_router(
        eligibility_router,
        prefix="/api",
        tags=["eligibility"],
    )

    return app


app = create_app()