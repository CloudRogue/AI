from __future__ import annotations

import json
import os
from typing import Literal, Optional, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from app.services.pipeline_runner import PipelineRunner
from app.services.openai.onboarding_ai_service import OnboardingAiService, QuestionItem
from app.services.openai.openai_client import OpenAIClient

router = APIRouter()

Publisher = Literal["LH", "SH"]


# -----------------------------
# Request / Response Models
# -----------------------------

class IngestQuestion(BaseModel):
    title: str
    description: str
    question: str


class IngestJsonRequest(BaseModel):
    link: str = Field(..., description="공고 링크")
    publisher: Publisher
    questions: List[IngestQuestion]


class AnswerItem(BaseModel):
    title: str
    value: Optional[str]  # string or null


# -----------------------------
# Helpers
# -----------------------------

def _parse_questions_json(questions_json: str) -> List[IngestQuestion]:
    try:
        raw = json.loads(questions_json)
        if not isinstance(raw, list):
            raise ValueError("QUESTIONS_JSON must be a JSON array")
        return [IngestQuestion.model_validate(item) for item in raw]
    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid QUESTIONS_JSON: {e}")


def _get_required_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        raise RuntimeError(f"Missing required env: {name}")
    return str(v).strip()


def _build_service() -> OnboardingAiService:

    prompt_path = _get_required_env("PROMPT_PATH")

    runner = PipelineRunner()
    client = OpenAIClient()

    return OnboardingAiService(
        runner=runner,
        prompt_path=prompt_path,
        client=client,
    )


# -----------------------------
# Route
# -----------------------------

@router.post("/ingest", response_model=List[AnswerItem])
async def ingest(request: Request) -> List[AnswerItem]:
    """

    1) application/json
    {
      "link": "...",
      "publisher": "LH" | "SH",
      "questions": [
        {"title": "...", "description": "...", "question": "..."}
      ]
    }

    2) form-data / x-www-form-urlencoded
      - link: string
      - publisher: LH | SH
      - QUESTIONS_JSON: JSON array string
    """

    content_type = (request.headers.get("content-type") or "").lower()

    link: str
    publisher: Publisher
    questions: List[IngestQuestion]

    # -------------------------
    # Parse Request
    # -------------------------
    if content_type.startswith("application/json"):
        try:
            body = await request.json()
            req = IngestJsonRequest.model_validate(body)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")

        link = req.link.strip()
        publisher = req.publisher
        questions = req.questions

    else:
        form = await request.form()

        link = (form.get("link") or "").strip()
        publisher_raw = (form.get("publisher") or "").strip().upper()
        questions_json = form.get("QUESTIONS_JSON")

        if not link:
            raise HTTPException(status_code=400, detail="Missing form field: link")
        if publisher_raw not in ("LH", "SH"):
            raise HTTPException(status_code=400, detail="Invalid form field: publisher (must be LH or SH)")
        if not questions_json:
            raise HTTPException(status_code=400, detail="Missing form field: QUESTIONS_JSON")

        publisher = publisher_raw  # type: ignore
        questions = _parse_questions_json(str(questions_json))

    if not questions:
        raise HTTPException(status_code=400, detail="questions is empty")

    # -------------------------
    # Build Service
    # -------------------------
    try:
        service = _build_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server configuration error: {e}")

    # -------------------------
    # Run Pipeline
    # -------------------------
    try:
        q_items = [
            QuestionItem(
                title=q.title,
                description=q.description,
                question=q.question,
            )
            for q in questions
        ]

        result = service.run(
            publisher=publisher,
            link=link,
            questions=q_items,
        )

        return [
            AnswerItem(title=item["title"], value=item.get("value"))
            for item in result
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ingest failed: {e}")