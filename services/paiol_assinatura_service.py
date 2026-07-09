"""Assinaturas em documentos críticos do Paiol."""

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models import PaiolAssinatura


def registrar_assinatura(
    db: Session,
    ctx: dict,
    documento_tipo: str,
    documento_id: int,
    observacao: str | None = None,
) -> PaiolAssinatura:
    payload = f"{documento_tipo}:{documento_id}:{ctx['user_id']}:{datetime.utcnow().isoformat()}"
    hash_registro = hashlib.sha256(payload.encode()).hexdigest()
    ass = PaiolAssinatura(
        documento_tipo=documento_tipo,
        documento_id=documento_id,
        user_id=ctx["user_id"],
        hash_registro=hash_registro,
        observacao=observacao,
    )
    db.add(ass)
    db.flush()
    return ass


def listar_assinaturas(db: Session, limit: int = 200) -> list[PaiolAssinatura]:
    return (
        db.query(PaiolAssinatura)
        .options(joinedload(PaiolAssinatura.user))
        .order_by(PaiolAssinatura.created_at.desc())
        .limit(limit)
        .all()
    )


def assinaturas_documento(db: Session, documento_tipo: str, documento_id: int) -> list[PaiolAssinatura]:
    return (
        db.query(PaiolAssinatura)
        .options(joinedload(PaiolAssinatura.user))
        .filter(
            PaiolAssinatura.documento_tipo == documento_tipo,
            PaiolAssinatura.documento_id == documento_id,
        )
        .order_by(PaiolAssinatura.created_at)
        .all()
    )
