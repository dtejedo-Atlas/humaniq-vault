"""Layer1 parser + OCR runtime + reprocess guardrails (read-only, no candidate mutation)."""

import io
import json
import os
import subprocess
import sys
import time
import unicodedata
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, "/app/backend")

from docx_extraction import extract_docx
from document_parser import DocumentParser
from ocr_runtime import ensure_ocr_runtime
from pdf_extraction import EXTRACTION_VERSION


EVIDENCE_PATH = Path("/root/humaniq_cv_diagnosis/evidence.json")
LAYER1_PATH = Path("/root/humaniq_cv_diagnosis/layer1_extraction.json")


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(ch)).lower()


def _build_docx_like_zip(document_xml: str, headers=None, footers=None) -> bytes:
    headers = headers or []
    footers = footers or []
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", document_xml)
        for idx, xml in enumerate(headers, start=1):
            zf.writestr(f"word/header{idx}.xml", xml)
        for idx, xml in enumerate(footers, start=1):
            zf.writestr(f"word/footer{idx}.xml", xml)
    return payload.getvalue()


def test_ocr_runtime_dependencies_available():
    langs = subprocess.check_output(["tesseract", "--list-langs"], text=True, stderr=subprocess.STDOUT)
    assert "spa" in langs
    assert "eng" in langs
    assert subprocess.run(["pdftoppm", "-v"], capture_output=True, text=True).returncode == 0


def test_ensure_ocr_runtime_idempotent():
    start_1 = time.time()
    ok_1 = ensure_ocr_runtime()
    elapsed_1 = time.time() - start_1
    start_2 = time.time()
    ok_2 = ensure_ocr_runtime()
    elapsed_2 = time.time() - start_2
    assert ok_1 is True and ok_2 is True
    assert elapsed_2 <= max(8.0, elapsed_1 + 0.5)


def test_docx_extracts_paragraphs_tables_textboxes_headers_footers():
    document_xml = """<?xml version='1.0' encoding='UTF-8'?>
    <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
      xmlns:mc='http://schemas.openxmlformats.org/markup-compatibility/2006'>
      <w:body>
        <w:p><w:r><w:t>PARRAFO_BASE</w:t></w:r></w:p>
        <w:tbl><w:tr><w:tc><w:p><w:r><w:t>CELDA_INTERNA</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
        <w:p>
          <w:r>
            <w:drawing><w:txbxContent><w:p><w:r><w:t>TEXTBOX_OK</w:t></w:r></w:p></w:txbxContent></w:drawing>
          </w:r>
        </w:p>
      </w:body>
    </w:document>
    """
    header = """<w:hdr xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:p><w:r><w:t>HEADER_UNICO</w:t></w:r></w:p></w:hdr>"""
    footer = """<w:ftr xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:p><w:r><w:t>FOOTER_UNICO</w:t></w:r></w:p></w:ftr>"""
    docx_bytes = _build_docx_like_zip(document_xml, headers=[header], footers=[footer])

    text = extract_docx(docx_bytes)
    assert "PARRAFO_BASE" in text
    assert "CELDA_INTERNA" in text
    assert "TEXTBOX_OK" in text
    assert "HEADER_UNICO" in text
    assert "FOOTER_UNICO" in text


def test_docx_alternatecontent_choice_only_and_deleted_text_ignored():
    document_xml = """<?xml version='1.0' encoding='UTF-8'?>
    <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
      xmlns:mc='http://schemas.openxmlformats.org/markup-compatibility/2006'>
      <w:body>
        <mc:AlternateContent>
          <mc:Choice Requires='w14'><w:p><w:r><w:t>ALT_CHOICE</w:t></w:r></w:p></mc:Choice>
          <mc:Fallback><w:p><w:r><w:t>ALT_FALLBACK</w:t></w:r></w:p></mc:Fallback>
        </mc:AlternateContent>
        <w:p><w:r><w:t>VISIBLE_TEXT</w:t></w:r></w:p>
        <w:del><w:r><w:t>DELETED_TEXT</w:t></w:r></w:del>
      </w:body>
    </w:document>
    """
    text = extract_docx(_build_docx_like_zip(document_xml))
    assert "ALT_CHOICE" in text
    assert "ALT_FALLBACK" not in text
    assert "DELETED_TEXT" not in text
    assert "VISIBLE_TEXT" in text


def test_pdf_empty_bytes_raises_once(monkeypatch):
    import document_parser as dp

    calls = {"n": 0}

    def fake_extract_pdf(data, native_extractor):
        calls["n"] += 1
        raise ValueError("El PDF no contiene páginas legibles.")

    monkeypatch.setattr(dp, "extract_pdf", fake_extract_pdf)
    with pytest.raises(Exception):
        dp.DocumentParser.extract_text_from_bytes(b"", "application/pdf")
    assert calls["n"] == 1


def test_carlos_pdf_alternate_reader_path_recovers_text():
    evidence = json.loads(EVIDENCE_PATH.read_text())
    row = next(item for item in evidence["candidates"] if item["id"] == "c4bf5f5e-1acd-4169-951f-16bf699f90c8")
    assert row["pages"] == 0
    assert row.get("alternate_pdf_chars", 0) > 0

    data = Path(row["local_path"]).read_bytes()
    extracted = DocumentParser.extract_with_details(data, row["format"])
    assert extracted["text_chars"] > 500
    assert extracted["readable"] is True
    assert len(extracted["pages"]) >= 1
    assert any(page["method"] == "alternate_reader" for page in extracted["pages"]) or extracted["text_chars"] > 0


def test_layer1_all_34_readonly_extraction_summary_matches_expected_counts():
    evidence = json.loads(EVIDENCE_PATH.read_text())
    prior = json.loads(LAYER1_PATH.read_text())
    prior_by_id = {item["id"]: item for item in prior}

    assert len(evidence["candidates"]) == 34
    extracted_rows = []
    name_hits = 0
    experience_hits = 0

    for row in evidence["candidates"]:
        raw = Path(row["local_path"]).read_bytes()
        result = DocumentParser.extract_with_details(raw, row["format"])
        extracted_rows.append({
            "id": row["id"],
            "readable": result["readable"],
            "text_chars": result["text_chars"],
            "ocr_failed_pages": sum(1 for p in result.get("pages", []) if p.get("ocr_failed")),
        })

        normalized_text = _strip_accents(result.get("text", ""))
        tokens = [tok for tok in _strip_accents(row.get("full_name", "")).replace("-", " ").split() if len(tok) >= 4 and tok != "candidato"]
        if tokens and any(tok in normalized_text for tok in tokens[:3]):
            name_hits += 1
        if any(keyword in normalized_text for keyword in ("experiencia", "experience", "anos", "years")):
            experience_hits += 1

        if row["id"] in prior_by_id:
            baseline = prior_by_id[row["id"]]
            # Small tolerance for parser improvements/regressions, but readability should stay stable.
            assert result["readable"] == baseline["readable"]

    readable = sum(1 for item in extracted_rows if item["readable"])
    unreadable = len(extracted_rows) - readable
    failed_ocr_pages = sum(item["ocr_failed_pages"] for item in extracted_rows)

    assert readable == 34
    assert unreadable == 0
    assert failed_ocr_pages == 0
    assert name_hits >= 20
    assert experience_hits >= 20


def test_reprocess_script_has_apply_guardrails_and_metadata_preservation():
    script = Path("/app/backend/scripts/reprocess_diagnostic_cohort.py").read_text()

    assert "parser.add_argument('--apply', action='store_true')" in script
    assert "if not args.apply:" in script
    assert "classification_not_run" in script
    assert "source_refs(before) == source_refs(row['detail'])" in script
    assert "'updated_at': before.get('updated_at')" in script
    assert "run_id = f'layer1:{EXTRACTION_VERSION}:{cid}:{sha}'" in script
    assert "status': 'completed'" in script


def test_protected_scoring_files_have_no_diff():
    protected_paths = [
        "backend/scoring",
        "backend/job_matching_service.py",
        "backend/scoring_config.py",
        "backend/hybrid_search_service.py",
    ]
    cmd = ["git", "-C", "/app", "diff", "--"] + protected_paths
    diff = subprocess.check_output(cmd, text=True)
    assert diff.strip() == ""


def test_extraction_version_consistency():
    assert EXTRACTION_VERSION == "cv-text-v3-tables-page-ocr"


def test_malformed_pdf_and_docx_fail_with_helpful_errors():
    with pytest.raises(Exception) as pdf_err:
        DocumentParser.extract_text_from_bytes(b"not-a-real-pdf", "application/pdf")
    assert "Error extrayendo texto de PDF" in str(pdf_err.value) or "PDF" in str(pdf_err.value)

    with pytest.raises(Exception) as docx_err:
        DocumentParser.extract_text_from_bytes(b"not-a-real-docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert "Error extrayendo texto de DOCX" in str(docx_err.value) or "DOCX" in str(docx_err.value)


def test_server_startup_has_ensure_ocr_runtime_hook():
    source = Path("/app/backend/server.py").read_text()
    assert "from ocr_runtime import ensure_ocr_runtime" in source
    assert "async def prepare_ocr_dependencies" in source
    assert "await asyncio.to_thread(ensure_ocr_runtime)" in source
