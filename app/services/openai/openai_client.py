from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str


class OpenAIClient:
    """
    - env에서 OPENAI_API_KEY / OPENAI_MODEL 읽음
    - Files API로 PDF 업로드 -> file_id
      * purpose는 'user_data' 사용 (Responses에서 파일 입력 용도)
    - Responses API에 input_file(file_id) + input_text 로 요청
    - (추가) Responses API에 input_text만으로 요청 (텍스트 전용)
    """

    def __init__(self, cfg: Optional[OpenAIConfig] = None):
        if cfg is None:
            api_key = os.getenv("OPENAI_API_KEY")
            model = os.getenv("OPENAI_MODEL")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required")
            if not model:
                raise RuntimeError("OPENAI_MODEL is required")
            cfg = OpenAIConfig(api_key=api_key, model=model)

        self.cfg = cfg
        self._files_url = "https://api.openai.com/v1/files"
        self._responses_url = "https://api.openai.com/v1/responses"

    # -------------------------
    # Files API
    # -------------------------
    def upload_pdf(self, pdf_bytes: bytes, *, filename: str = "document.pdf", timeout: int = 120) -> str:
        """
        PDF bytes 업로드 후 file_id 반환.

        목적(purpose):
        - 'responses'는 허용되지 않음
        - PDF를 모델 입력으로 쓰는 경우 공식 가이드 예시대로 'user_data' 사용
        """
        if not pdf_bytes:
            raise ValueError("pdf_bytes is empty")

        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}

        # multipart/form-data
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        data = {"purpose": "user_data"}

        r = requests.post(self._files_url, headers=headers, files=files, data=data, timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI Files API error {r.status_code}: {r.text}")

        j = r.json()
        file_id = j.get("id")
        if not file_id:
            raise RuntimeError(f"OpenAI Files API: file id missing. resp={j}")
        return str(file_id)

    # -------------------------
    # Responses API
    # -------------------------
    def create_response_with_pdf(
        self,
        *,
        user_text: str,
        file_id: str,
        timeout: int = 180,
    ) -> Dict[str, Any]:
        """
        Responses API:
        - input: [{role:'user', content:[{type:'input_file', file_id}, {type:'input_text', text:user_text}]}]
        """
        if not user_text.strip():
            raise ValueError("user_text is empty")
        if not file_id.strip():
            raise ValueError("file_id is empty")

        headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.cfg.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file_id},
                        {"type": "input_text", "text": user_text},
                    ],
                }
            ],
        }

        r = requests.post(self._responses_url, headers=headers, json=body, timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI API error {r.status_code}: {r.text}")
        return r.json()

    def create_response_text_only(
        self,
        *,
        user_text: str,
        timeout: int = 180,
    ) -> Dict[str, Any]:
        """
        Responses API (텍스트 전용):
        - input: [{role:'user', content:[{type:'input_text', text:user_text}]}]
        """
        if not user_text.strip():
            raise ValueError("user_text is empty")

        headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.cfg.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_text},
                    ],
                }
            ],
        }

        r = requests.post(self._responses_url, headers=headers, json=body, timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI API error {r.status_code}: {r.text}")
        return r.json()

    @staticmethod
    def extract_output_text(resp_json: Dict[str, Any]) -> str:
        """
        Responses API 응답에서 텍스트 추출.
        - output_text가 있으면 사용
        - 없으면 output[].content[].text 조합
        """
        if not isinstance(resp_json, dict):
            raise RuntimeError("invalid OpenAI response (not a dict)")

        ot = resp_json.get("output_text")
        if isinstance(ot, str) and ot.strip():
            return ot

        out = resp_json.get("output")
        if isinstance(out, list):
            chunks: list[str] = []
            for item in out:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    t = c.get("text")
                    if isinstance(t, str) and t:
                        chunks.append(t)
            if chunks:
                return "\n".join(chunks)

        raise RuntimeError("OpenAI response text not found")