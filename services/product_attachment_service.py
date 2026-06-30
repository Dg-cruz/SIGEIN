"""Upload e gestão de anexos de produtos (PDF, PNG, JPEG até 10 MB)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from models import ProductAttachment

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "product_attachments"
MAX_BYTES = 10 * 1024 * 1024

_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
}


def _safe_extension(filename: str) -> str | None:
    ext = Path(filename or "").suffix.lower()
    if ext == ".jpeg":
        return ".jpg"
    return ext if ext in _ALLOWED_EXTENSIONS else None


def _normalize_content_type(content_type: str | None, ext: str) -> str:
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct in _ALLOWED_CONTENT_TYPES:
        return "image/jpeg" if ct in {"image/jpg", "image/pjpeg"} else ct
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".png":
        return "image/png"
    return "image/jpeg"


def _attachment_dir(product_id: int) -> Path:
    return UPLOAD_ROOT / str(product_id)


def attachment_file_path(attachment: ProductAttachment) -> Path:
    return _attachment_dir(attachment.product_id) / attachment.stored_name


def _is_upload_file(value) -> bool:
    return hasattr(value, "filename") and hasattr(value, "read")


async def save_product_attachments(
    db: Session,
    product_id: int,
    user_id: int | None,
    uploads: list,
) -> str | None:
    """Salva anexos enviados. Retorna mensagem de erro ou None."""
    files = [f for f in uploads if _is_upload_file(f) and (f.filename or "").strip()]
    if not files:
        return None

    dest_dir = _attachment_dir(product_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        original_name = Path(upload.filename or "").name.strip()
        if not original_name:
            continue

        ext = _safe_extension(original_name)
        if not ext:
            return f'Arquivo "{original_name}" não permitido. Use PDF, PNG ou JPEG.'

        content = await upload.read()
        if not content:
            continue
        if len(content) > MAX_BYTES:
            return f'Arquivo "{original_name}" excede o limite de 10 MB.'

        content_type = _normalize_content_type(upload.content_type, ext)
        stored_name = f"{uuid.uuid4().hex}{ext}"
        target = dest_dir / stored_name
        target.write_bytes(content)

        db.add(
            ProductAttachment(
                product_id=product_id,
                filename=original_name,
                stored_name=stored_name,
                content_type=content_type,
                size_bytes=len(content),
                created_by=user_id,
            )
        )

    db.commit()
    return None


def remove_product_attachments(
    db: Session,
    product_id: int,
    attachment_ids: list[int],
) -> None:
    if not attachment_ids:
        return
    rows = (
        db.query(ProductAttachment)
        .filter(
            ProductAttachment.product_id == product_id,
            ProductAttachment.id.in_(attachment_ids),
        )
        .all()
    )
    for row in rows:
        path = attachment_file_path(row)
        if path.is_file():
            path.unlink()
        db.delete(row)
    db.commit()
    _cleanup_empty_dir(product_id)


def delete_all_product_attachments(db: Session, product_id: int) -> None:
    rows = (
        db.query(ProductAttachment)
        .filter(ProductAttachment.product_id == product_id)
        .all()
    )
    for row in rows:
        path = attachment_file_path(row)
        if path.is_file():
            path.unlink()
        db.delete(row)
    db.commit()
    shutil.rmtree(_attachment_dir(product_id), ignore_errors=True)


def _cleanup_empty_dir(product_id: int) -> None:
    folder = _attachment_dir(product_id)
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()


def format_file_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"
