from __future__ import annotations

from typing import Iterable, Iterator, Tuple
import requests


SH_INNO_URL = "https://www.i-sh.co.kr/main/com/file/innoFD.do"

SH_BRD_ID_FIXED = "GS0401"
SH_FILE_TP_FIXED = "A"


def download_sh_file_bytes(
    *,
    seq: str,
    file_seq: str,
    timeout: int = 30,
) -> Tuple[bytes, str]:
    """
    GET /main/com/file/innoFD.do?brdId=GS0401&seq=...&fileTp=A&fileSeq=...
    반환: (content_bytes, content_type)
    """
    r = requests.get(
        SH_INNO_URL,
        params={
            "brdId": SH_BRD_ID_FIXED,
            "seq": seq,
            "fileTp": SH_FILE_TP_FIXED,
            "fileSeq": file_seq,
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    r.raise_for_status()

    data = r.content
    content_type = r.headers.get("Content-Type", "")

    # 방어: HTML 오류 페이지면 실패 처리
    head = data[:300].lstrip().lower()
    if head.startswith(b"<html") or b"<html" in head:
        raise RuntimeError(f"Expected file bytes but got HTML (Content-Type={content_type}).")

    return data, content_type


def iter_download_sh_files(
    *,
    seq: str,
    file_seqs: Iterable[str],
    timeout: int = 30,
) -> Iterator[dict]:
    """
    fileSeq 배열만큼 순회하며 다운로드 bytes를 yield.
    yield:
      - fileSeq
      - bytes
      - contentType
    """
    for fs in file_seqs:
        b, ct = download_sh_file_bytes(
            seq=seq,
            file_seq=str(fs),
            timeout=timeout,
        )
        yield {"fileSeq": str(fs), "bytes": b, "contentType": ct}