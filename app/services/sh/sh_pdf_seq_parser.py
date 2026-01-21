from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup


DOWNLIST_RE = re.compile(
    r"initParam\.downList\s*=\s*(\[\s*\{.*?\}\s*\])\s*;",
    re.DOTALL,
)


@dataclass(frozen=True)
class ShSeqAndFileSeqs:
    seq: str
    file_seqs: List[str]


def extract_seq(url: str) -> str:
    """
    URL에서 query param 'seq'만 신뢰해서 추출.
    앞단 경로/다른 파라미터가 뭐가 오든 상관없음.
    """
    parsed = urlparse(url.strip())
    qs = parse_qs(parsed.query)
    seq_list = qs.get("seq")
    if not seq_list or not seq_list[0].strip():
        raise ValueError("URL query param 'seq' not found")
    return seq_list[0].strip()


def extract_file_seqs_from_html(html: str) -> List[str]:
    """
    HTML 내 script에서 initParam.downList = [...] 를 찾아 JSON 파싱 후 fileSeq만 추출.
    """
    soup = BeautifulSoup(html, "html.parser")
    script_text = "\n".join((s.string or s.get_text() or "") for s in soup.find_all("script"))

    m = DOWNLIST_RE.search(script_text)
    if not m:
        raise ValueError("initParam.downList not found in HTML")

    downlist_raw = m.group(1)
    downlist: List[dict[str, Any]] = json.loads(downlist_raw)

    return [str(item["fileSeq"]) for item in downlist if "fileSeq" in item]


def fetch_seq_and_file_seqs(url: str, *, timeout: int = 20) -> ShSeqAndFileSeqs:
    seq = extract_seq(url)

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    r.raise_for_status()

    file_seqs = extract_file_seqs_from_html(r.text)
    return ShSeqAndFileSeqs(seq=seq, file_seqs=file_seqs)