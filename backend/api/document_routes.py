from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.auth_dependencies import get_current_user, require_csrf
from app.config import settings
from app.schemas import DocumentExtractionResponse
from services.document_extraction_service import (
    DocumentExtractionError,
    extract_document,
    upload_limit_detail,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/extract",
    response_model=DocumentExtractionResponse,
    dependencies=[Depends(get_current_user), Depends(require_csrf)],
)
async def extract_uploaded_document(
    file: UploadFile = File(...),
) -> DocumentExtractionResponse:
    try:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(status_code=413, detail=upload_limit_detail())
        result = extract_document(file.filename, file.content_type, content)
        return DocumentExtractionResponse(
            filename=result.filename,
            content_type=result.content_type,
            file_size_bytes=result.file_size_bytes,
            text=result.text,
            extraction_method=result.extraction_method,
            pages_processed=result.pages_processed,
            ocr_pages=list(result.ocr_pages),
        )
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    finally:
        await file.close()
