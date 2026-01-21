from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from app.services.openai.openai_client import OpenAIClient


class EligibilityAiService:
    """
    prompts/eligibility.txt 프롬프트 + (REQUIREMENTS_JSON, ANSWERS_JSON) 입력으로
    자격요건 진단 JSON을 반환.
    """

    def __init__(self) -> None:
        self._client = OpenAIClient()
        self._prompt_path = self._resolve_prompt_path()

    @staticmethod
    def _resolve_prompt_path() -> Path:

        prompts_dir = os.getenv("PROMPTS_DIR")
        if prompts_dir:
            return Path(prompts_dir) / "eligibility.txt"

        # app/services/openai/eligibility_ai_service.py -> parents[2] == app/
        return Path(__file__).resolve().parents[2] / "prompts" / "eligibility.txt"

    def _load_prompt(self) -> str:
        if not self._prompt_path.exists():
            raise RuntimeError(f"eligibility prompt not found: {self._prompt_path}")
        return self._prompt_path.read_text(encoding="utf-8")

    def diagnose(
        self,
        *,
        requirements: List[Dict[str, Any]],
        answers: List[Dict[str, Any]],
        timeout: int = 180,
    ) -> Dict[str, Any]:
        prompt = self._load_prompt()

        payload = {
            "REQUIREMENTS_JSON": requirements,
            "ANSWERS_JSON": answers,
        }

        # 프롬프트가 "반드시 JSON만 출력"을 강제하므로,
        # user_text는 프롬프트 + 입력 JSON을 그대로 포함한다.
        user_text = (
            prompt
            + "\n\n"
            + "REQUIREMENTS_JSON:\n"
            + json.dumps(payload["REQUIREMENTS_JSON"], ensure_ascii=False)
            + "\n\n"
            + "ANSWERS_JSON:\n"
            + json.dumps(payload["ANSWERS_JSON"], ensure_ascii=False)
        )

        resp = self._client.create_response_text_only(user_text=user_text, timeout=timeout)
        text = self._client.extract_output_text(resp).strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            # 프롬프트 규칙 위반(설명/마크다운 등) 대비
            raise RuntimeError(f"LLM returned non-JSON output: {e}. head={text[:400]!r}")

        if not isinstance(result, dict):
            raise RuntimeError("LLM output JSON is not an object")

        # 최소 구조 검증(나머지는 response_model이 한 번 더 잡아줌)
        if "supportStatus" not in result or "trace" not in result:
            raise RuntimeError("LLM output JSON missing required keys: supportStatus/trace")

        return result