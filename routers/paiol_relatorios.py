"""Relatórios operacionais do módulo Paiol."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from services.paiol_helpers import user_context
from services.paiol_relatorios_service import (
    build_relatorios_resumo,
    csv_filename,
    export_estoque_csv,
    export_movimentacoes_csv,
    export_requisicoes_csv,
)
from templating import templates

router = APIRouter(prefix="/paiol", tags=["Paiol — Relatórios"])


def _auth(user: str):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


@router.get("/relatorios")
def relatorios(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    resumo = build_relatorios_resumo(db, ctx["orgao_id"])
    return templates.TemplateResponse(
        "paiol/relatorios.html",
        {"request": request, "hide_app_header": True, "resumo": resumo},
    )


@router.get("/relatorios/export/estoque.csv")
def export_estoque(user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    content = export_estoque_csv(db, ctx["orgao_id"])
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{csv_filename("estoque_paiol")}"'},
    )


@router.get("/relatorios/export/movimentacoes.csv")
def export_movimentacoes(user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    content = export_movimentacoes_csv(db, ctx["orgao_id"])
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{csv_filename("movimentacoes_paiol")}"'},
    )


@router.get("/relatorios/export/requisicoes.csv")
def export_requisicoes(user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    content = export_requisicoes_csv(db, ctx["orgao_id"])
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{csv_filename("requisicoes_paiol")}"'},
    )
