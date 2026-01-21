from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QuestionItem:
    title: str
    description: str
    question: str


def load_prompt(prompt_path: str) -> str:
    p = Path(prompt_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    txt = p.read_text(encoding="utf-8")

    # 최소 검증: placeholder 존재 여부
    if "{{QUESTIONS_JSON}}" not in txt:
        raise ValueError("Prompt missing placeholder: {{QUESTIONS_JSON}}")
    return txt


class OpenAIRequestBuilder:
    def __init__(self, *, prompt_path: str):
        self.prompt_template = load_prompt(prompt_path)

    def build_payload(
        self,
        *,
        model: str,
        questions: list[QuestionItem],
        pdf_bytes: bytes,
        filename: str = "document.pdf",
    ) -> dict[str, Any]:
        questions_json = [
            {"title": q.title, "description": q.description, "question": q.question}
            for q in questions
        ]
        q_dump = json.dumps(questions_json, ensure_ascii=False)

        prompt = self.prompt_template.replace("{{QUESTIONS_JSON}}", q_dump)

        file_data_b64 = base64.b64encode(pdf_bytes).decode("ascii")

        return {
            "model": model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": filename,
                            "file_data": file_data_b64,
                        }
                    ],
                },
            ],
            # 출력 형식 강제: JSON 배열(title, value)
            "text": {
                "format": {
                    "type": "json_schema",
                    "strict": True,
                    "name": "onboarding_answers",
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["title", "value"],
                            "properties": {
                                "title": {"type": "string"},
                                "value": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                            },
                        },
                    },
                }
            },
        }