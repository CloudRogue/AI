from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.services.pipeline_runner import PipelineRunner, DocumentSource, DocumentMeta
from app.services.openai.openai_client import OpenAIClient


@dataclass(frozen=True)
class QuestionItem:
    title: str
    description: str
    question: str


class OnboardingAiService:
    """
    파이프라인:
    - publisher + link -> PDF bytes 다운로드 (서버에서 OCR/텍스트추출/페이지 split 안 함)
    - PDF bytes -> Files API 업로드 -> file_id
    - prompt(txt) 로드
    - 질문(questions)은 JSON으로 input_text에 넣어 전달
    - Responses API에 input_file + input_text로 전송
    - 응답 텍스트를 JSON 배열로 파싱해서 반환
      (입력 questions 개수/순서 동일, 각 원소: {title, value})
    """

    def __init__(self, runner: PipelineRunner, prompt_path: str, client: OpenAIClient):
        self.runner = runner
        self.prompt_path = prompt_path  # 상대경로 운영 규칙(루트에서 실행)을 전제
        self.client = client

    def run(
        self,
        *,
        publisher: str,
        link: str,
        questions: Union[List[Dict[str, Any]], List[QuestionItem]],
        timeout: int = 180,
    ) -> List[Dict[str, Any]]:
        # 1) PDF bytes 다운로드
        meta, pdf_bytes = self.runner.download_pdf_bytes(
            DocumentSource(publisher=publisher, url=link)
        )
        if not pdf_bytes:
            raise RuntimeError("downloaded PDF is empty")

        # 2) PDF 업로드 -> file_id (base64 금지)
        file_id = self.client.upload_pdf(
            pdf_bytes,
            filename=meta.filename or "document.pdf",
            timeout=timeout,
        )

        # 3) 프롬프트 로드
        prompt_template = self._load_prompt_text(self.prompt_path)

        # 4) questions 정규화(= JSON 배열)
        questions_json = self._normalize_questions(questions)

        # 5) 모델에 전달할 input_text (JSON 문자열)
        user_text = self._build_user_text(
            prompt_template=prompt_template,
            meta=meta,
            publisher=publisher,
            link=link,
            questions_json=questions_json,
        )

        # 6) Responses 호출 (PDF는 input_file로 첨부)
        resp = self.client.create_response_with_pdf(
            user_text=user_text,
            file_id=file_id,
            timeout=timeout,
        )

        # 7) 텍스트 추출 -> JSON 배열 파싱
        text = self.client.extract_output_text(resp)
        parsed = self._parse_json_array(text)

        # 8) 최종 형태 강제(입력 순서/개수 유지, title은 입력 그대로)
        return self._coerce_output(questions_json, parsed)

    # -------------------------
    # Prompt
    # -------------------------
    def _load_prompt_text(self, prompt_path: str) -> str:
        p = Path(prompt_path)
        return p.read_text(encoding="utf-8")

    # -------------------------
    # Questions normalization
    # -------------------------
    def _normalize_questions(
        self, questions: Union[List[Dict[str, Any]], List[QuestionItem]]
    ) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for q in questions:
            if isinstance(q, QuestionItem):
                out.append(
                    {"title": q.title, "description": q.description, "question": q.question}
                )
            elif isinstance(q, dict):
                out.append(
                    {
                        "title": str(q.get("title", "")),
                        "description": str(q.get("description", "")),
                        "question": str(q.get("question", "")),
                    }
                )
            else:
                raise TypeError(f"invalid question item type: {type(q)}")
        return out

    # -------------------------
    # Input text (JSON)
    # -------------------------
    def _build_user_text(
        self,
        *,
        prompt_template: str,
        meta: DocumentMeta,
        publisher: str,
        link: str,
        questions_json: List[Dict[str, str]],
    ) -> str:
        """
        PDF는 input_file로 첨부되므로, 여기서는 지시문/질문만 전달.
        질문은 JSON으로 준다(네 요청).
        출력은 JSON 배열만 요구한다.
        """
        payload = {
            "system_prompt": prompt_template,
            "document_meta": {
                "publisher": publisher,
                "source_url": link,
                "filename": meta.filename,
                "content_type": meta.content_type,
            },
            "questions_json": questions_json,
            "output_rules": {
                "only_json_array": True,
                "keep_length_and_order": True,
                "title_must_match_input": True,
                "value_type": "string_or_null",
                "format_example": [
                    {"title": "<input title>", "value": "<string or null>"}
                ],
            },
            "note": "A PDF is attached to this message as a file. Read it to answer questions_json.",
        }
        return json.dumps(payload, ensure_ascii=False)

    # -------------------------
    # Output parsing / coercion
    # -------------------------
    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        t = text.strip()

        # 1) 직파싱
        try:
            obj = json.loads(t)
            if isinstance(obj, list):
                return obj  # type: ignore[return-value]
        except Exception:
            pass

        # 2) 앞뒤 잡설 제거: 첫 '[' ~ 마지막 ']'
        l = t.find("[")
        r = t.rfind("]")
        if l != -1 and r != -1 and l < r:
            sliced = t[l : r + 1]
            obj = json.loads(sliced)
            if isinstance(obj, list):
                return obj  # type: ignore[return-value]

        raise RuntimeError("model output is not a JSON array")

    def _coerce_output(
        self,
        questions_json: List[Dict[str, str]],
        parsed: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        최종 강제:
        - 입력 질문 개수/순서 그대로
        - title은 입력 title 그대로
        - value는 str 또는 None만 허용 (그 외는 None 처리)
        """
        out: List[Dict[str, Any]] = []

        for i, q in enumerate(questions_json):
            title = q.get("title")
            value: Optional[str] = None

            if i < len(parsed) and isinstance(parsed[i], dict):
                v = parsed[i].get("value")
                if v is None:
                    value = None
                elif isinstance(v, str):
                    value = v
                else:
                    value = None

            out.append({"title": title, "value": value})

        return out