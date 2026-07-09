"""Atalhos personalizados da dashboard Paiol."""

from sqlalchemy.orm import Session

from models import PaiolDashboardAtalho
from paiol_constants import PAIOL_MENU_BY_KEY, PAIOL_MENU_CATALOG


def _resolve(item: PaiolDashboardAtalho) -> dict | None:
    meta = PAIOL_MENU_BY_KEY.get(item.menu_key)
    if not meta:
        return None
    return {
        "id": item.id,
        "menu_key": item.menu_key,
        "sort_order": item.sort_order,
        **meta,
    }


def list_user_shortcuts(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(PaiolDashboardAtalho)
        .filter(PaiolDashboardAtalho.user_id == user_id)
        .order_by(PaiolDashboardAtalho.sort_order, PaiolDashboardAtalho.id)
        .all()
    )
    out = []
    for row in rows:
        resolved = _resolve(row)
        if resolved:
            out.append(resolved)
    return out


def list_available_shortcuts(db: Session, user_id: int) -> list[dict]:
    used = {
        r.menu_key
        for r in db.query(PaiolDashboardAtalho.menu_key)
        .filter(PaiolDashboardAtalho.user_id == user_id)
        .all()
    }
    return [item for item in PAIOL_MENU_CATALOG if item["key"] not in used]


def add_shortcut(db: Session, user_id: int, menu_key: str) -> dict:
    if menu_key not in PAIOL_MENU_BY_KEY:
        raise ValueError("Atalho inválido")

    exists = (
        db.query(PaiolDashboardAtalho)
        .filter(
            PaiolDashboardAtalho.user_id == user_id,
            PaiolDashboardAtalho.menu_key == menu_key,
        )
        .first()
    )
    if exists:
        raise ValueError("Atalho já adicionado")

    count = db.query(PaiolDashboardAtalho).filter(PaiolDashboardAtalho.user_id == user_id).count()
    row = PaiolDashboardAtalho(user_id=user_id, menu_key=menu_key, sort_order=count)
    db.add(row)
    db.commit()
    db.refresh(row)
    resolved = _resolve(row)
    if not resolved:
        raise ValueError("Atalho inválido")
    return resolved


def remove_shortcut(db: Session, user_id: int, atalho_id: int) -> bool:
    row = (
        db.query(PaiolDashboardAtalho)
        .filter(
            PaiolDashboardAtalho.id == atalho_id,
            PaiolDashboardAtalho.user_id == user_id,
        )
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
