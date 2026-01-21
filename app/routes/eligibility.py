from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.openai.eligibility_ai_service import EligibilityAiService

router = APIRouter(tags=["eligibility"])


class SupportStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    PENDING = "PENDING"


class RequirementItem(BaseModel):
    additionalOnboardingId: int = Field(..., ge=0)
    key: str
    value: str


class AnswerItem(BaseModel):
    additionalOnboardingId: int = Field(..., ge=0)
    value: Optional[str] = None


class EligibilityDiagnoseRequest(BaseModel):
    REQUIREMENTS_JSON: List[RequirementItem]
    ANSWERS_JSON: List[AnswerItem]


class TraceItem(BaseModel):
    additionalOnboardingId: Optional[int] = None
    key: str
    passed: bool
    message: str


class EligibilityDiagnoseResponse(BaseModel):
    supportStatus: SupportStatus
    trace: List[TraceItem]


_service = EligibilityAiService()


@router.post("/eligibility/diagnose", response_model=EligibilityDiagnoseResponse)
def diagnose(req: EligibilityDiagnoseRequest) -> Any:
    try:
        result: Dict[str, Any] = _service.diagnose(
            requirements=[r.model_dump() for r in req.REQUIREMENTS_JSON],
            answers=[a.model_dump() for a in req.ANSWERS_JSON],
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"eligibility diagnose failed: {e!s}")