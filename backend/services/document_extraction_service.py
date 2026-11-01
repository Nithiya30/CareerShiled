import io
import re
import shutil
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

import pymupdf
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError
from PIL import Image, UnidentifiedImageError

from app.config import settings


MAX_PDF_PAGES = 30
MAX_IMAGE_PIXELS = 40_000_000
MAX_DOCX_ENTRIES = 1_000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_TEXT_CHARS = 1_000_000
OCR_RENDER_SCALE = 1.7
OCR_TIMEOUT_SECONDS = 15

SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class DocumentExtractionError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class ExtractionResult:
    filename: str
    content_type: str
    file_size_bytes: int
    text: str
    extraction_method: str
    pages_processed: int = 0
    ocr_pages: tuple[int, ...] = ()


def _safe_filename(filename: str | None) -> str:
    if not filename:
        raise DocumentExtractionError(400, "A filename is required.")
    normalized = filename.replace("\\", "/").rsplit("/", 1)[-1]
    safe_name = "".join(character for character in normalized if character.isprintable())[:255]
    if safe_name in {"", ".", ".."}:
        raise DocumentExtractionError(400, "The uploaded filename is invalid.")
    return safe_name


def upload_limit_detail() -> str:
    limit = settings.MAX_UPLOAD_SIZE_BYTES
    formatted_limit = (
        f"{limit / (1024 * 1024):g} MiB"
        if limit >= 1024 * 1024
        else f"{limit} bytes"
    )
    return f"Files must be no larger than {formatted_limit}."


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        character
        for character in normalized
        if character in "\n\t" or unicodedata.category(character) != "Cc"
    )
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in normalized.split("\n")]
    normalized = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if len(normalized) > MAX_EXTRACTED_TEXT_CHARS:
        raise DocumentExtractionError(
            413,
            "The extracted text is too large to analyze. Upload a shorter document.",
        )
    if not normalized:
        raise DocumentExtractionError(
            422,
            "No readable text was found. Upload a clearer document or enter the job description manually.",
        )
    return normalized


def _validate_docx_archive(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise DocumentExtractionError(422, "The Word document contains too many embedded files.")
            expanded_size = 0
            names = set()
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                    raise DocumentExtractionError(422, "The Word document package is invalid.")
                expanded_size += entry.file_size
                if expanded_size > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise DocumentExtractionError(413, "The Word document expands beyond the supported size.")
                if entry.file_size > 0 and entry.compress_size == 0:
                    raise DocumentExtractionError(422, "The Word document package is invalid.")
                if entry.flag_bits & 0x1:
                    raise DocumentExtractionError(422, "Encrypted Word documents are not supported.")
                if entry.compress_size > 0 and entry.file_size / entry.compress_size > 200:
                    raise DocumentExtractionError(422, "The Word document package has an unsafe compression ratio.")
                names.add(entry.filename)
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise DocumentExtractionError(422, "The uploaded file is not a valid DOCX document.")
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        raise DocumentExtractionError(422, "The Word document is corrupted or invalid.") from exc


def _extract_docx(content: bytes) -> str:
    _validate_docx_archive(content)
    try:
        document = Document(io.BytesIO(content))
    except (PackageNotFoundError, XMLSyntaxError, KeyError, ValueError, OSError, RuntimeError) as exc:
        raise DocumentExtractionError(422, "The Word document is corrupted or invalid.") from exc

    content_parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            content_parts.append("\t".join(cell.text for cell in row.cells))
    for section in document.sections:
        content_parts.extend(paragraph.text for paragraph in section.header.paragraphs)
        content_parts.extend(paragraph.text for paragraph in section.footer.paragraphs)
    return "\n".join(content_parts)


def _ocr_image(image: Image.Image) -> str:
    import pytesseract

    configured_command = settings.TESSERACT_CMD
    executable = (
        str(Path(configured_command).expanduser())
        if configured_command and Path(configured_command).expanduser().is_file()
        else shutil.which(configured_command or pytesseract.pytesseract.tesseract_cmd)
    )
    if not executable:
        raise DocumentExtractionError(
            503,
            "OCR is unavailable. Install Tesseract OCR, add it to PATH, or set "
            "TESSERACT_CMD to the executable's full path.",
        )
    pytesseract.pytesseract.tesseract_cmd = executable
    try:
        return pytesseract.image_to_string(
            image,
            lang="eng",
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise DocumentExtractionError(
            503,
            "OCR is unavailable. Install Tesseract OCR and ensure tesseract.exe is on PATH, "
            "or set TESSERACT_CMD to its full path.",
        ) from exc
    except (pytesseract.TesseractError, RuntimeError) as exc:
        raise DocumentExtractionError(
            503,
            "OCR could not process this document. Check the Tesseract installation and English language data.",
        ) from exc


def _open_image(content: bytes, expected_format: str | None = None) -> Image.Image:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image_format = image.format
            if expected_format and image_format != expected_format:
                raise DocumentExtractionError(
                    415,
                    "The image contents do not match the filename extension.",
                )
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise DocumentExtractionError(413, "The image dimensions exceed the supported limit.")
            image.load()
            return image.convert("RGB")
    except UnidentifiedImageError as exc:
        raise DocumentExtractionError(422, "The uploaded image is corrupted or invalid.") from exc
    except Image.DecompressionBombError as exc:
        raise DocumentExtractionError(413, "The image dimensions exceed the supported limit.") from exc
    except OSError as exc:
        raise DocumentExtractionError(422, "The uploaded image is corrupted or invalid.") from exc


def _extract_pdf(content: bytes) -> tuple[str, int, tuple[int, ...], str]:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise DocumentExtractionError(422, "The PDF is corrupted or invalid.") from exc
    with document:
        if document.needs_pass:
            raise DocumentExtractionError(422, "Password-protected PDFs are not supported.")
        if document.page_count > MAX_PDF_PAGES:
            raise DocumentExtractionError(
                413,
                f"PDFs may contain at most {MAX_PDF_PAGES} pages.",
            )
        if document.page_count == 0:
            raise DocumentExtractionError(422, "The PDF has no pages.")
        page_count = document.page_count

        page_text = []
        ocr_pages = []
        has_embedded_text = False
        for page_number, page in enumerate(document, start=1):
            try:
                text = page.get_text("text")
            except (RuntimeError, ValueError) as exc:
                raise DocumentExtractionError(422, "The PDF contains a page that could not be read.") from exc
            if len(text.strip()) < 40:
                page_width = page.rect.width * OCR_RENDER_SCALE
                page_height = page.rect.height * OCR_RENDER_SCALE
                if page_width <= 0 or page_height <= 0 or page_width * page_height > MAX_IMAGE_PIXELS:
                    raise DocumentExtractionError(413, "A PDF page exceeds the supported image dimensions.")
                try:
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE),
                        alpha=False,
                    )
                except (RuntimeError, ValueError) as exc:
                    raise DocumentExtractionError(422, "A PDF page could not be rendered for OCR.") from exc
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                text = f"{text}\n{_ocr_image(image)}".strip()
                ocr_pages.append(page_number)
            else:
                has_embedded_text = True
            page_text.append(text)

    method = (
        "pdf_text_and_ocr"
        if ocr_pages and has_embedded_text
        else "pdf_ocr"
        if ocr_pages
        else "pdf_text"
    )
    return "\n".join(page_text), page_count, tuple(ocr_pages), method


def extract_document(
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> ExtractionResult:
    safe_name = _safe_filename(filename)
    extension = PurePosixPath(safe_name).suffix.lower()
    expected_mime = SUPPORTED_MIME_TYPES.get(extension)
    if expected_mime is None:
        raise DocumentExtractionError(
            415,
            "Unsupported file type. Upload a PDF, PNG, JPG, JPEG, WEBP, DOCX, or TXT file.",
        )
    normalized_mime = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_mime != expected_mime:
        raise DocumentExtractionError(
            415,
            "The file's MIME type does not match its supported extension.",
        )
    if not content:
        raise DocumentExtractionError(422, "The uploaded file is empty.")
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise DocumentExtractionError(413, upload_limit_detail())

    pages_processed = 0
    ocr_pages: tuple[int, ...] = ()
    if extension == ".txt":
        if b"\x00" in content:
            raise DocumentExtractionError(415, "The TXT file contains binary data, not plain text.")
        try:
            raw_text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError(415, "TXT files must use UTF-8 text encoding.") from exc
        method = "txt"
    elif extension == ".docx":
        if not content.startswith(b"PK"):
            raise DocumentExtractionError(415, "The file contents do not match a DOCX document.")
        raw_text = _extract_docx(content)
        method = "docx"
    elif extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise DocumentExtractionError(415, "The file contents do not match a PDF document.")
        raw_text, pages_processed, ocr_pages, method = _extract_pdf(content)
    else:
        expected_format = {
            ".png": "PNG",
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".webp": "WEBP",
        }[extension]
        image = _open_image(content, expected_format)
        raw_text = _ocr_image(image)
        method = "image_ocr"

    text = _normalize_text(raw_text)
    return ExtractionResult(
        filename=safe_name,
        content_type=expected_mime,
        file_size_bytes=len(content),
        text=text,
        extraction_method=method,
        pages_processed=pages_processed,
        ocr_pages=ocr_pages,
    )
