from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple, List
import io

from app.services.lh.lh_pdf_downloader import download_lh_pdf_bytes
from app.services.lh.lh_pdf_parser import extract_single_pdf_file_id

from app.services.sh.sh_pdf_seq_parser import fetch_seq_and_file_seqs
from app.services.sh.sh_pdf_downloader import iter_download_sh_files


Publisher = Literal["LH", "SH"]


@dataclass(frozen=True)
class DocumentSource:
    publisher: Publisher
    url: str


@dataclass(frozen=True)
class DocumentMeta:
    publisher: Publisher
    source_url: str
    filename: str
    content_type: str


def _merge_pdfs_bytes(pdfs: List[bytes]) -> bytes:
    """
    여러 PDF bytes를 '페이지 단위'로 병합해서 하나의 PDF bytes로 반환.
    (텍스트 추출/OCR/split 아님. 단순 병합)
    """
    from pypdf import PdfReader, PdfWriter  # pip install pypdf

    writer = PdfWriter()

    for b in pdfs:
        if not b:
            continue
        reader = PdfReader(io.BytesIO(b))
        for page in reader.pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class PipelineRunner:
    """
    - (LH/SH) 공고 링크 -> 원본 PDF bytes 1개 확보 (split 안 함)
    - 정책:
      - LH: PDF 1개 (기존 파서/다운로더 그대로)
      - SH: PDF 여러 개 가능 -> 병합해서 1개로 반환
    """

    def download_pdf_bytes(
        self,
        src: DocumentSource,
        *,
        timeout: int = 30,
    ) -> Tuple[DocumentMeta, bytes]:
        if src.publisher == "LH":
            return self._download_lh_pdf(src.url, timeout=timeout)
        if src.publisher == "SH":
            return self._download_sh_pdf(src.url, timeout=timeout)
        raise ValueError(f"unsupported publisher: {src.publisher}")

    # -------------------------
    # LH (단일 PDF 유지)
    # -------------------------
    def _download_lh_pdf(self, url: str, *, timeout: int = 30) -> Tuple[DocumentMeta, bytes]:
        """
        LH:
        - 공고 상세 HTML에서 fileDownLoad('숫자') 형태로 PDF file_id 1개를 파싱
        - /lhapply/lhFile.do?fileid=... 로 PDF bytes 다운로드
        """
        html = self._http_get_text(url, timeout=timeout)

        file_id = extract_single_pdf_file_id(html)
        pdf_bytes, content_type = download_lh_pdf_bytes(file_id, timeout=timeout)

        meta = DocumentMeta(
            publisher="LH",
            source_url=url,
            filename=f"{file_id}.pdf",
            content_type=content_type or "application/pdf",
        )
        return meta, pdf_bytes

    # -------------------------
    # SH (여러 PDF 병합)
    # -------------------------
    def _download_sh_pdf(self, url: str, *, timeout: int = 30) -> Tuple[DocumentMeta, bytes]:
        """
        SH:
        - fetch_seq_and_file_seqs(url)로 seq + fileSeq 리스트 확보
        - iter_download_sh_files(seq=..., file_seqs=...)로 다운로드
        - PDF 후보들을 전부 모아 병합 후 1개 PDF로 반환
        """
        parsed = fetch_seq_and_file_seqs(url, timeout=timeout)

        # fileSeq -> pdf bytes (PDF로 판별된 것만)
        pdf_map: dict[str, bytes] = {}

        for item in iter_download_sh_files(
            seq=parsed.seq,
            file_seqs=parsed.file_seqs,
            timeout=timeout,
        ):
            ct = (item.get("contentType") or "").lower()
            b = item.get("bytes") or b""
            fs = str(item.get("fileSeq") or "")

            if not fs or not b:
                continue

            # 1차: content-type
            if "application/pdf" in ct:
                pdf_map[fs] = b
                continue

            # 2차: magic header
            head = b[:20].lstrip()
            if head.startswith(b"%PDF-"):
                pdf_map[fs] = b

        if not pdf_map:
            raise RuntimeError("SH: no PDF attachment found")

        ordered_pdfs: List[bytes] = [pdf_map[fs] for fs in parsed.file_seqs if fs in pdf_map]

        if not ordered_pdfs:
            raise RuntimeError("SH: PDF attachments exist but none matched ordering (unexpected)")

        merged = _merge_pdfs_bytes(ordered_pdfs) if len(ordered_pdfs) > 1 else ordered_pdfs[0]

        meta = DocumentMeta(
            publisher="SH",
            source_url=url,
            filename=f"sh_{parsed.seq}_merged.pdf" if len(ordered_pdfs) > 1 else f"sh_{parsed.seq}.pdf",
            content_type="application/pdf",
        )
        return meta, merged

    # -------------------------
    # Internal HTTP helper
    # -------------------------
    def _http_get_text(self, url: str, *, timeout: int = 30) -> str:
        import requests

        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        r.raise_for_status()
        return r.text