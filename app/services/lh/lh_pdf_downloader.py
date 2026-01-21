from __future__ import annotations

from typing import Tuple
import requests

LH_DOWNLOAD_URL = "https://apply.lh.or.kr/lhapply/lhFile.do"

def download_lh_pdf_bytes(file_id: str, *, timeout: int = 30) -> Tuple[bytes, str]:

    r = requests.get(
        LH_DOWNLOAD_URL,
        params={"fileid": file_id},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    r.raise_for_status()

    content_type = r.headers.get("Content-Type", "")
    data = r.content

    head = data[:300].lstrip().lower()
    if head.startswith(b"<html") or b"<html" in head:
        raise RuntimeError(f"Expected PDF bytes but got HTML (Content-Type={content_type}).")

    return data, content_type