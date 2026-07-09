"""Rotas de segurança do módulo Paiol (custódia, assinaturas, logs, permissões)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from services.audit_logs_service import log_list_template_context
from services.paiol_assinatura_service import listar_assinaturas
from services.paiol_custodia_service import listar_eventos
from services.paiol_helpers import user_context
from templating import templates

router = APIRouter(prefix="/paiol/seguranca", tags=["Paiol — Segurança"])


def _auth(user: str):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


@router.get("/custodia")
def seguranca_custodia(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    eventos = listar_eventos(db, ctx["orgao_id"])
    return templates.TemplateResponse(
        "paiol/seguranca_custodia.html",
        {"request": request, "hide_app_header": True, "eventos": eventos},
    )


@router.get("/assinaturas")
def seguranca_assinaturas(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    assinaturas = listar_assinaturas(db)
    return templates.TemplateResponse(
        "paiol/seguranca_assinaturas.html",
        {"request": request, "hide_app_header": True, "assinaturas": assinaturas},
    )


@router.get("/permissoes")
def seguranca_permissoes(user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    return RedirectResponse("/paiol/cadastro/usuarios-autorizados", status_code=302)


@router.get("/logs")
def seguranca_logs(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    return templates.TemplateResponse(
        "logs_list.html",
        log_list_template_context(db, user, request, paiol_only=True),
    )
