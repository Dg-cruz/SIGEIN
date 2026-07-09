"""Helpers compartilhados do módulo Paiol."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import PaiolFabricante, PaiolMunicao, User


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


def opcoes_campos_tipo_material(db: Session) -> dict:
    fabricantes = (
        db.query(PaiolFabricante)
        .filter(PaiolFabricante.ativo == True)
        .order_by(PaiolFabricante.nome)
        .all()
    )
    municoes = (
        db.query(PaiolMunicao)
        .filter(PaiolMunicao.ativo == True)
        .order_by(PaiolMunicao.calibre)
        .all()
    )
    return {
        "fabricantes": [{"value": f.nome, "label": f.nome, "id": f.id} for f in fabricantes],
        "calibres": [
            {
                "value": m.calibre,
                "label": f"{m.calibre} — {m.nome_comercial}" if m.nome_comercial else m.calibre,
                "id": m.id,
            }
            for m in municoes
        ],
    }
