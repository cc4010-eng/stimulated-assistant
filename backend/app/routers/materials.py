import uuid
from pathlib import PurePath

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.models import Material, Study
from app.pipeline import process_material
from app.schemas import MaterialDetail, MaterialOut
from app.storage import FileTooLarge, Storage, get_storage
from app.transcription import Transcriber, get_transcriber

router = APIRouter(tags=["materials"])

ALLOWED_PREFIXES = ("audio/", "video/")


@router.post(
    "/studies/{study_id}/materials",
    response_model=MaterialDetail,
    status_code=status.HTTP_201_CREATED,
)
def upload_material(
    study_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
    transcriber: Transcriber = Depends(get_transcriber),
) -> Material:
    if db.get(Study, study_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study not found")

    content_type = file.content_type or ""
    if not content_type.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload an audio or video file")

    material_id = str(uuid.uuid4())
    suffix = PurePath(file.filename or "").suffix.lower()[:10]
    key = f"{study_id}/{material_id}{suffix}"
    try:
        size = storage.save(key, file.file, settings.max_upload_mb * 1024 * 1024)
    except FileTooLarge:
        raise HTTPException(
            413,
            f"File is larger than {settings.max_upload_mb} MB",
        ) from None

    material = Material(
        id=material_id,
        study_id=study_id,
        filename=PurePath(file.filename or "recording").name[:255],
        content_type=content_type,
        size_bytes=size,
        storage_key=key,
    )
    db.add(material)
    db.commit()

    # Runs inline for now; this call is what moves to a queue later.
    process_material(material_id, db, storage, transcriber)
    return _get_material(material_id, db)


@router.get("/studies/{study_id}/materials", response_model=list[MaterialOut])
def list_materials(study_id: str, db: Session = Depends(get_db)) -> list[Material]:
    if db.get(Study, study_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study not found")
    stmt = (
        select(Material).where(Material.study_id == study_id).order_by(Material.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.get("/materials/{material_id}", response_model=MaterialDetail)
def get_material(material_id: str, db: Session = Depends(get_db)) -> Material:
    return _get_material(material_id, db)


@router.get("/materials/{material_id}/file")
def get_material_file(
    material_id: str,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> FileResponse:
    material = _get_material(material_id, db)
    path = storage.path(material.storage_key)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is missing from storage")
    return FileResponse(path, media_type=material.content_type)


def _get_material(material_id: str, db: Session) -> Material:
    material = db.get(
        Material, material_id, options=[selectinload(Material.segments)], populate_existing=True
    )
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    return material
