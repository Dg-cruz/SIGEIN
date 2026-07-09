"""Helpers compartilhados do módulo Paiol."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import User


def get_user_row(db: Session, email: str) -> User:
    row = db.query(User).filter(User.email == email).first()
    if not row:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return row


def user_context(db: Session, email: str) -> dict:
    u = get_user_row(db, email)
    return {
        "user_id": u.id,
        "municipio_id": u.municipio_id,
        "orgao_id": u.orgao_id,
        "unidade_id": u.unidade_id,
        "user": u,
    }
