"""Central de Atendimento e Despacho (CAD)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import User
from templating import templates

router = APIRouter(prefix="/cad", tags=["CAD"])

# Itens do menu / cards do painel (evoluem com o módulo)
CAD_MENU = (
    {
        "key": "painel",
        "label": "Painel operacional",
        "subtitle": "Visão geral da central",
        "icon": "fa-gauge-high",
        "url": "/cad",
    },
    {
        "key": "ocorrencias",
        "label": "Ocorrências",
        "subtitle": "Registro e acompanhamento de chamados",
        "icon": "fa-phone-volume",
        "url": "/cad/ocorrencias",
    },
    {
        "key": "despacho",
        "label": "Despacho",
        "subtitle": "Distribuição de equipes e viaturas",
        "icon": "fa-tower-broadcast",
        "url": "/cad/despacho",
    },
    {
        "key": "recursos",
        "label": "Recursos",
        "subtitle": "Viaturas, equipes e postos",
        "icon": "fa-car-side",
        "url": "/cad/recursos",
    },
    {
        "key": "relatorios",
        "label": "Relatórios",
        "subtitle": "Indicadores e exportações",
        "icon": "fa-chart-column",
        "url": "/cad/relatorios",
    },
    {
        "key": "configuracoes",
        "label": "Configurações",
        "subtitle": "Tipos, prioridades e perfis da central",
        "icon": "fa-gear",
        "url": "/cad/configuracoes",
    },
)


def _user_obj(db: Session, user: str) -> User | None:
    if not user:
        return None
    return db.query(User).filter(User.email == user).first()


def _render_pagina(
    request: Request,
    db: Session,
    user: str,
    *,
    titulo: str,
    descricao: str,
    menu_key: str,
    template: str = "cad/pagina.html",
):
    if not user:
        return RedirectResponse("/login")
    u = _user_obj(db, user)
    if not u:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "titulo": titulo,
            "descricao": descricao,
            "menu_key": menu_key,
            "cad_menu": CAD_MENU,
        },
    )


@router.get("")
@router.get("/")
def cad_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    u = _user_obj(db, user)
    if not u:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        "cad/dashboard.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "cad_menu": CAD_MENU,
            "menu_key": "painel",
        },
    )


@router.get("/ocorrencias")
def cad_ocorrencias(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Ocorrências",
        descricao="Registro, classificação e acompanhamento de chamados da central.",
        menu_key="ocorrencias",
    )


@router.get("/despacho")
def cad_despacho(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Despacho",
        descricao="Fila operacional e envio de recursos para atendimento.",
        menu_key="despacho",
    )


@router.get("/recursos")
def cad_recursos(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Recursos",
        descricao="Viaturas, equipes, postos e disponibilidade em tempo real.",
        menu_key="recursos",
    )


@router.get("/relatorios")
def cad_relatorios(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Relatórios",
        descricao="Indicadores de atendimento, tempos de resposta e produtividade.",
        menu_key="relatorios",
    )


@router.get("/configuracoes")
def cad_configuracoes(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Configurações",
        descricao="Tipos de ocorrência, prioridades, turnos e parâmetros da central.",
        menu_key="configuracoes",
    )
