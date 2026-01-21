# pdf_attachment_id_extractor.py
# pip install beautifulsoup4

from __future__ import annotations

import re
from typing import Optional
from bs4 import BeautifulSoup

FILE_DOWNLOAD_RE = re.compile(r"""fileDownLoad\(\s*(['"])(\d+)\1\s*\)""", re.IGNORECASE)


def extract_single_pdf_file_id(html: str) -> str:
    """
    <div class="bbsV_atchmnfl"> 안에서
    href="javascript:fileDownLoad('숫자');" 형태의 링크 중
    링크 텍스트가 '.pdf'로 끝나는 1개를 찾아 file_id를 반환.
    - PDF가 없으면 ValueError
    - PDF가 2개 이상이면 ValueError (가정 위반 방지)
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("div.bbsV_atchmnfl")
    if not root:
        raise ValueError("attachment container not found: div.bbsV_atchmnfl")

    found: Optional[str] = None

    for a in root.select("a[href]"):
        href = a.get("href") or ""
        if "fileDownLoad" not in href:
            continue

        text = (a.get_text(strip=True) or "").lower()
        if not text.endswith(".pdf"):
            continue

        m = FILE_DOWNLOAD_RE.search(href)
        if not m:
            continue

        file_id = m.group(2)
        if found is not None and found != file_id:
            raise ValueError(f"multiple pdf attachments found: {found}, {file_id}")
        found = file_id

    if not found:
        raise ValueError("pdf attachment not found")

    return found


if __name__ == "__main__":
    sample = r"""
    <div class="bbsV_atchmnfl">
      <ul class="bbsV_link file">
        <li><a href="javascript:fileDownLoad('64851760');">xxx.hwp</a></li>
        <li><a href="javascript:fileDownLoad('64767994');">아무거나이름이바뀌어도됨.pdf</a></li>
      </ul>
    </div>
    """
    print(extract_single_pdf_file_id(sample))  # 64767994