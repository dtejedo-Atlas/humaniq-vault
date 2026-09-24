"""Unit tests for StorageService.upload_resume retry/fail-fast behavior."""

import pytest
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage_service import APP_NAME, ResumeStorageError, StorageService


def _http_error(status_code):
    response = requests.Response()
    response.status_code = status_code
    error = requests.HTTPError(f"HTTP {status_code}")
    error.response = response
    return error


# Module: storage_service.upload_resume retry policy
def test_upload_resume_retries_transient_and_reuses_same_object_key(monkeypatch):
    attempts = []

    def fake_put(path, data, content_type, timeout=None):
        attempts.append({"path": path, "timeout": timeout, "content_type": content_type, "size": len(data)})
        if len(attempts) < 3:
            raise _http_error(503)
        return {"path": path, "size": len(data)}

    monkeypatch.setattr(StorageService, "put_object", staticmethod(fake_put))
    monkeypatch.setattr("storage_service.time.sleep", lambda *_: None)

    out = StorageService.upload_resume(b"pdf-bytes", "cand-1", "resume.pdf", "application/pdf")

    assert len(attempts) == 3
    assert len({entry["path"] for entry in attempts}) == 1
    assert all(entry["timeout"] == (10, 30) for entry in attempts)
    assert out["storage_path"].startswith(f"{APP_NAME}/resumes/cand-1/")
    assert out["content_type"] == "application/pdf"


def test_upload_resume_exhausts_after_three_transient_attempts(monkeypatch):
    calls = {"n": 0}

    def fake_put(*_args, **_kwargs):
        calls["n"] += 1
        raise _http_error(504)

    monkeypatch.setattr(StorageService, "put_object", staticmethod(fake_put))
    monkeypatch.setattr("storage_service.time.sleep", lambda *_: None)

    with pytest.raises(ResumeStorageError) as exc:
        StorageService.upload_resume(b"abc", "cand-2", "resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    assert calls["n"] == 3
    assert exc.value.attempts == 3
    assert "guardado remoto" in str(exc.value)


@pytest.mark.parametrize("status_code", [400, 401, 402, 403, 439])
def test_upload_resume_fails_fast_on_permanent_provider_errors(monkeypatch, status_code):
    calls = {"n": 0}

    def fake_put(*_args, **_kwargs):
        calls["n"] += 1
        raise _http_error(status_code)

    monkeypatch.setattr(StorageService, "put_object", staticmethod(fake_put))
    monkeypatch.setattr("storage_service.time.sleep", lambda *_: None)

    with pytest.raises(ResumeStorageError) as exc:
        StorageService.upload_resume(b"abc", "cand-3", "resume.pdf", "application/pdf")

    assert calls["n"] == 1
    assert exc.value.attempts == 1
    assert str(status_code) not in str(exc.value)
