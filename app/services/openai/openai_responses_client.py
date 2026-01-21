from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import requests


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_sec: int = 90


class OpenAIResponsesClient:
    def __init__(self, cfg: OpenAIConfig):
        self.cfg = cfg

    def create(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.cfg.base_url}/responses"
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.cfg.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.cfg.timeout_sec,
        )
        r.raise_for_status()
        data = r.json()

        text = _extract_output_text(data)
        if text is None:
            raise RuntimeError("OpenAI response missing output_text")

        try:
            parsed = json.loads(text)
        except Exception as e:
            raise RuntimeError(f"Model output is not valid JSON: {e}\nRAW={text[:400]}")

        if not isinstance(parsed, list):
            raise RuntimeError("Model output JSON is not an array")

        return parsed


def _extract_output_text(resp: dict[str, Any]) -> Optional[str]:
    out = resp.get("output")
    if not isinstance(out, list):
        return None
    for item in out:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                return part.get("text")
    return None