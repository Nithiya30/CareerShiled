import io
import uuid

import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import routes as api_routes
from app.config import settings
from app.db import Base, get_db
from app.main import app
from services import document_extraction_service as extraction_service
from services.document_extraction_service import (
    DocumentExtractionError,
    extract_document,
)
from services.rate_limit_service import rate_limiter


@pytest.fixture
def document_client():
    rate_limiter.clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            registration = client.post(
                "/api/auth/register",
                json={
                    "name": "Document Test",
                    "email": f"document-{uuid.uuid4()}@example.test",
                    "password": "document test password",
                },
            )
            assert registration.status_code == 201
            client.headers.update(
                {"X-CSRF-Token": client.cookies.get("careershield_csrf")}
            )
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limiter.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _pdf_bytes(text: str | None = None) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    if text:
        page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def _scanned_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image(page.rect, stream=_image_bytes())
    content = document.tobytes()
    document.close()
    return content


def _docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Requirements"
    table.cell(0, 1).text = "Python and teamwork"
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _image_bytes(image_format: str = "PNG") -> bytes:
    image = Image.new("RGB", (120, 60), "white")
    output = io.BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def _mock_ocr(text: str):
    def recognize(image):
        assert image.mode == "RGB"
        return text

    return recognize


def test_extract_pdf_text():
    expected = "Seeking a software engineer to build secure APIs and collaborate with a remote team."
    result = extract_document("job.pdf", "application/pdf", _pdf_bytes(expected))
    assert expected in result.text
    assert result.extraction_method == "pdf_text"
    assert result.pages_processed == 1
    assert result.ocr_pages == ()


def test_extract_scanned_pdf_uses_ocr(monkeypatch):
    content = _scanned_pdf_bytes()
    monkeypatch.setattr(
        extraction_service,
        "_ocr_image",
        _mock_ocr("Scanned job advertisement text"),
    )
    result = extract_document("scan.pdf", "application/pdf", content)
    assert result.text == "Scanned job advertisement text"
    assert result.extraction_method == "pdf_ocr"
    assert result.ocr_pages == (1,)


def test_extract_docx_includes_paragraphs_and_tables():
    result = extract_document(
        "job.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _docx_bytes("Software Engineer"),
    )
    assert "Software Engineer" in result.text
    assert "Requirements" in result.text
    assert "Python and teamwork" in result.text
    assert result.extraction_method == "docx"


def test_extract_txt_normalizes_line_endings_and_whitespace():
    result = extract_document("job.txt", "text/plain", b"\xef\xbb\xbf  Job title  \r\n\r\n  Engineer  ")
    assert result.text == "Job title\n\nEngineer"
    assert result.extraction_method == "txt"


def test_extract_image_uses_local_ocr(monkeypatch):
    monkeypatch.setattr(extraction_service, "_ocr_image", _mock_ocr("Image job text"))
    result = extract_document("job.png", "image/png", _image_bytes())
    assert result.text == "Image job text"
    assert result.extraction_method == "image_ocr"


@pytest.mark.parametrize(
    ("filename", "content_type", "image_format"),
    [
        ("job.png", "image/png", "PNG"),
        ("job.jpg", "image/jpeg", "JPEG"),
        ("job.jpeg", "image/jpeg", "JPEG"),
        ("job.webp", "image/webp", "WEBP"),
    ],
)
def test_extract_supported_image_formats(filename, content_type, image_format, monkeypatch):
    monkeypatch.setattr(extraction_service, "_ocr_image", _mock_ocr("Image job text"))
    result = extract_document(filename, content_type, _image_bytes(image_format))
    assert result.text == "Image job text"
    assert result.extraction_method == "image_ocr"


def test_ocr_uses_configured_tesseract_executable(tmp_path, monkeypatch):
    import pytesseract

    executable = tmp_path / "tesseract.exe"
    executable.write_bytes(b"mock executable")
    monkeypatch.setattr(settings, "TESSERACT_CMD", str(executable))
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    monkeypatch.setattr(pytesseract, "image_to_string", lambda image, lang, timeout: "Recognized text")

    result = extract_document("job.png", "image/png", _image_bytes())

    assert result.text == "Recognized text"
    assert pytesseract.pytesseract.tesseract_cmd == str(executable)


def test_ocr_rejects_missing_configured_tesseract_executable(monkeypatch):
    monkeypatch.setattr(
        settings,
        "TESSERACT_CMD",
        r"C:\missing\private\tesseract.exe",
    )
    monkeypatch.setattr(extraction_service.shutil, "which", lambda command: None)

    with pytest.raises(DocumentExtractionError) as error:
        extract_document("job.png", "image/png", _image_bytes())

    assert error.value.status_code == 503
    assert "TESSERACT_CMD" in error.value.detail
    assert "private" not in error.value.detail


def test_invalid_image_upload_is_rejected():
    with pytest.raises(DocumentExtractionError) as error:
        extract_document("job.png", "image/png", b"not an image")
    assert error.value.status_code == 422


def test_ocr_processing_failure_returns_safe_error(monkeypatch):
    import pytesseract

    def failed_ocr(image, lang, timeout):
        raise pytesseract.TesseractError(1, "sensitive executable output")

    monkeypatch.setattr(pytesseract, "image_to_string", failed_ocr)
    with pytest.raises(DocumentExtractionError) as error:
        extract_document("job.png", "image/png", _image_bytes())

    assert error.value.status_code == 503
    assert "sensitive executable output" not in error.value.detail


def test_invalid_extension_and_mime_are_rejected():
    with pytest.raises(DocumentExtractionError) as unsupported:
        extract_document("job.exe", "application/octet-stream", b"data")
    assert unsupported.value.status_code == 415

    with pytest.raises(DocumentExtractionError) as mismatch:
        extract_document("job.txt", "application/pdf", b"valid text")
    assert mismatch.value.status_code == 415


def test_empty_file_is_rejected():
    with pytest.raises(DocumentExtractionError) as error:
        extract_document("empty.txt", "text/plain", b"")
    assert error.value.status_code == 422


def test_oversized_file_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 4)
    with pytest.raises(DocumentExtractionError) as error:
        extract_document("large.txt", "text/plain", b"12345")
    assert error.value.status_code == 413


def test_corrupted_pdf_is_rejected():
    with pytest.raises(DocumentExtractionError) as error:
        extract_document("broken.pdf", "application/pdf", b"%PDF-1.7 not a valid document")
    assert error.value.status_code == 422


def test_image_without_readable_text_is_rejected(monkeypatch):
    monkeypatch.setattr(extraction_service, "_ocr_image", _mock_ocr(" \n\t "))
    with pytest.raises(DocumentExtractionError) as error:
        extract_document("blank.png", "image/png", _image_bytes())
    assert error.value.status_code == 422
    assert "clearer document" in error.value.detail


def test_missing_ocr_engine_returns_actionable_error(monkeypatch):
    import pytesseract

    def missing_engine(image, lang, timeout):
        assert image.mode == "RGB"
        assert lang == "eng"
        assert timeout > 0
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", missing_engine)
    with pytest.raises(DocumentExtractionError) as error:
        extract_document("job.png", "image/png", _image_bytes())
    assert error.value.status_code == 503
    assert "Tesseract OCR" in error.value.detail


def test_extraction_endpoint_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/documents/extract",
            files={"file": ("job.txt", b"Job description", "text/plain")},
        )
    assert response.status_code == 401


def test_extraction_endpoint_returns_text_and_safe_filename(document_client):
    response = document_client.post(
        "/api/documents/extract",
        files={
            "file": (
                r"C:\uploads\job.txt",
                b"Seeking an engineer for a remote software role.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "job.txt"
    assert data["text"] == "Seeking an engineer for a remote software role."
    assert data["file_size_bytes"] == len(b"Seeking an engineer for a remote software role.")
    assert data["extraction_method"] == "txt"


def test_extraction_endpoint_enforces_upload_size(document_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 4)
    response = document_client.post(
        "/api/documents/extract",
        files={"file": ("job.txt", b"12345", "text/plain")},
    )
    assert response.status_code == 413


def test_extraction_endpoint_rejects_unsupported_file_type(document_client):
    response = document_client.post(
        "/api/documents/extract",
        files={"file": ("job.exe", b"not allowed", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_extracted_text_uses_existing_local_analysis_pipeline(document_client, monkeypatch):
    description = (
        "URGENT hiring for a remote assistant. Send an upfront equipment fee by wire "
        "transfer before starting this position."
    )
    extracted = document_client.post(
        "/api/documents/extract",
        files={"file": ("job.txt", description.encode(), "text/plain")},
    )
    assert extracted.status_code == 200

    original_predict = api_routes.ml_service.predict
    observed_text = []

    def capture_local_prediction(text):
        observed_text.append(text)
        return original_predict(text)

    monkeypatch.setattr(api_routes.ml_service, "predict", capture_local_prediction)
    monkeypatch.setattr(api_routes.transformer_service, "analyze_text", pytest.fail)
    monkeypatch.setattr(api_routes.reputation_service, "analyze_live_verification", pytest.fail)
    monkeypatch.setattr(api_routes.domain_agent, "analyze", pytest.fail)
    analyzed = document_client.post(
        "/api/analyze",
        json={
            "job_title": "Uploaded Job Advertisement",
            "job_description": extracted.json()["text"],
            "document_source": True,
        },
    )

    assert analyzed.status_code == 200
    assert description in observed_text[0]
    assert analyzed.json()["ml_result"]["category"] == "ml"
    assert analyzed.json()["transformer_result"]["label"] == "SKIPPED"
