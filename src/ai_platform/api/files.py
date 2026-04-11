import json
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from ulid import ULID

from ai_platform.config import Settings
from ai_platform.dependencies import get_settings

router = APIRouter(prefix="/v1", tags=["files"])
logger = structlog.get_logger(__name__)

ALLOWED_EXTENSIONS = {
    # Text / code
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".sql",
    ".sh",
    ".log",
    # Documents
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".pptx",
    ".odt",
    ".ods",
    ".rtf",
    ".epub",
    # Images (accepted for upload, but no content extraction)
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
):
    """Upload a file and return its ID for use in chat."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

    # Read and check size
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )

    # Save file
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(ULID())
    safe_name = f"{file_id}{ext}"
    file_path = upload_dir / safe_name
    file_path.write_bytes(content)

    # Save metadata (original filename)
    meta_path = upload_dir / f"{file_id}.meta.json"
    meta_path.write_text(json.dumps({"filename": file.filename, "ext": ext, "size": len(content)}))

    await logger.ainfo("file_uploaded", file_id=file_id, name=file.filename, size=len(content))

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "ext": ext,
    }


def get_file_meta(upload_dir: Path, file_id: str) -> dict | None:
    """Read metadata for an uploaded file."""
    meta_path = upload_dir / f"{file_id}.meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return None


@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    settings: Settings = Depends(get_settings),
):
    """Download a previously uploaded file."""
    upload_dir = Path(settings.upload_dir)

    # Find file by ID prefix (ID + extension), excluding meta files
    matches = [p for p in upload_dir.glob(f"{file_id}.*") if ".meta." not in p.name]
    if not matches:
        raise HTTPException(status_code=404, detail="File not found")

    meta = get_file_meta(upload_dir, file_id)
    download_name = meta["filename"] if meta else matches[0].name

    return FileResponse(str(matches[0]), filename=download_name)
