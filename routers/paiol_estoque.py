"""Rotas operacionais de estoque do módulo Paiol."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND

from database import get_db
from dependencies import get_current_user
from services.paiol_audit import log_paiol
from models import PaiolDeposito, PaiolLocalizacao, PaiolMaterial
from paiol_constants import TipoMovimentacaoPaiol
from services.paiol_estoque_service import (
    PaiolEstoqueError,
    get_saldo_atual,
    registrar_ajuste,
    registrar_entrada,
    registrar_inventario,
    registrar_saida,
    registrar_transferencia,
)
from services.paiol_helpers import user_context
from templating import templates

router = APIRouter(prefix="/paiol/estoque", tags=["Paiol — Estoque"])

_OPERACOES = {
    TipoMovimentacaoPaiol.ENTRADA.value: {
        "titulo": "Entrada de estoque",
        "descricao": "Registro de recebimento de material no paiol.",
        "icone": "fa-arrow-down",
        "submit": "Registrar entrada",
    },
    TipoMovimentacaoPaiol.SAIDA.value: {
        "titulo": "Saída de estoque",
        "descricao": "Registro de saída de material do paiol.",
        "icone": "fa-arrow-up",
        "submit": "Registrar saída",
    },
    TipoMovimentacaoPaiol.TRANSFERENCIA.value: {
        "titulo": "Transferência",
        "descricao": "Movimentação de material entre depósitos ou localizações.",
        "icone": "fa-right-left",
        "submit": "Registrar transferência",
    },
    TipoMovimentacaoPaiol.AJUSTE.value: {
        "titulo": "Ajuste de estoque",
        "descricao": "Correção documentada de saldo com justificativa obrigatória.",
        "icone": "fa-sliders",
        "submit": "Registrar ajuste",
        "qty_label": "Nova quantidade",
    },
    TipoMovimentacaoPaiol.INVENTARIO.value: {
        "titulo": "Inventário",
        "descricao": "Contagem física e reconciliação do saldo.",
        "icone": "fa-clipboard-check",
        "submit": "Registrar inventário",
        "qty_label": "Quantidade contada",
    },
}


def _redirect_login(user: str):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


def _lists(db: Session, ctx: dict):
    materiais = (
        db.query(PaiolMaterial)
        .filter(
            PaiolMaterial.orgao_id == ctx["orgao_id"],
            PaiolMaterial.ativo == True,
            PaiolMaterial.controla_por_serie == False,
        )
        .order_by(PaiolMaterial.nome)
        .all()
    )
    depositos = (
        db.query(PaiolDeposito)
        .filter(PaiolDeposito.orgao_id == ctx["orgao_id"], PaiolDeposito.ativo == True)
        .order_by(PaiolDeposito.nome)
        .all()
    )
    localizacoes = (
        db.query(PaiolLocalizacao)
        .join(PaiolDeposito)
        .filter(PaiolDeposito.orgao_id == ctx["orgao_id"], PaiolLocalizacao.ativo == True)
        .order_by(PaiolLocalizacao.codigo)
        .all()
    )
    return materiais, depositos, localizacoes


def _render_form(request: Request, db: Session, user: str, operacao: str, error: str | None = None, **extra):
    ctx = user_context(db, user)
    materiais, depositos, localizacoes = _lists(db, ctx)
    meta = _OPERACOES[operacao]
    locs_json = [{"id": l.id, "deposito_id": l.deposito_id, "label": f"{l.codigo}" + (f" — {l.descricao}" if l.descricao else "")} for l in localizacoes]
    return templates.TemplateResponse(
        "paiol/forms/estoque_movimento_form.html",
        {
            "request": request,
            "hide_app_header": True,
            "operacao": operacao,
            "meta": meta,
            "materiais": materiais,
            "depositos": depositos,
            "localizacoes_json": locs_json,
            "error": error,
            **extra,
        },
    )

# ── Entrada ────────────────────────────────────────────────

@router.get("/entrada")
def entrada_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return _render_form(request, db, user, TipoMovimentacaoPaiol.ENTRADA.value)


@router.post("/entrada")
def entrada_post(
    request: Request,
    material_id: int = Form(...),
    deposito_destino_id: int = Form(...),
    localizacao_destino_id: Optional[int] = Form(None),
    quantidade: int = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    try:
        registrar_entrada(
            db,
            ctx,
            material_id,
            deposito_destino_id,
            quantidade,
            localizacao_destino_id or None,
            observacao.strip() or None,
        )
        log_paiol(db, user, request, f"Entrada de estoque — material #{material_id}, qtd {quantidade}")
        return RedirectResponse("/paiol/movimentacoes", status_code=HTTP_302_FOUND)
    except PaiolEstoqueError as e:
        return _render_form(request, db, user, TipoMovimentacaoPaiol.ENTRADA.value, str(e))


# ── Saída ──────────────────────────────────────────────────

@router.get("/saida")
def saida_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return _render_form(request, db, user, TipoMovimentacaoPaiol.SAIDA.value)


@router.post("/saida")
def saida_post(
    request: Request,
    material_id: int = Form(...),
    deposito_origem_id: int = Form(...),
    localizacao_origem_id: Optional[int] = Form(None),
    quantidade: int = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    try:
        registrar_saida(
            db,
            ctx,
            material_id,
            deposito_origem_id,
            quantidade,
            localizacao_origem_id or None,
            observacao.strip() or None,
        )
        log_paiol(db, user, request, f"Saída de estoque — material #{material_id}, qtd {quantidade}")
        return RedirectResponse("/paiol/movimentacoes", status_code=HTTP_302_FOUND)
    except PaiolEstoqueError as e:
        return _render_form(request, db, user, TipoMovimentacaoPaiol.SAIDA.value, str(e))


# ── Transferência ──────────────────────────────────────────

@router.get("/transferencia")
def transferencia_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return _render_form(request, db, user, TipoMovimentacaoPaiol.TRANSFERENCIA.value)


@router.post("/transferencia")
def transferencia_post(
    request: Request,
    material_id: int = Form(...),
    deposito_origem_id: int = Form(...),
    localizacao_origem_id: Optional[int] = Form(None),
    deposito_destino_id: int = Form(...),
    localizacao_destino_id: Optional[int] = Form(None),
    quantidade: int = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    try:
        registrar_transferencia(
            db,
            ctx,
            material_id,
            deposito_origem_id,
            deposito_destino_id,
            quantidade,
            localizacao_origem_id or None,
            localizacao_destino_id or None,
            observacao.strip() or None,
        )
        log_paiol(db, user, request, f"Transferência de estoque — material #{material_id}, qtd {quantidade}")
        return RedirectResponse("/paiol/movimentacoes", status_code=HTTP_302_FOUND)
    except PaiolEstoqueError as e:
        return _render_form(request, db, user, TipoMovimentacaoPaiol.TRANSFERENCIA.value, str(e))


# ── Ajuste ─────────────────────────────────────────────────

@router.get("/ajustes")
def ajuste_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return _render_form(request, db, user, TipoMovimentacaoPaiol.AJUSTE.value)


@router.post("/ajustes")
def ajuste_post(
    request: Request,
    material_id: int = Form(...),
    deposito_id: int = Form(...),
    localizacao_id: Optional[int] = Form(None),
    quantidade_nova: int = Form(...),
    observacao: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    try:
        registrar_ajuste(db, ctx, material_id, deposito_id, quantidade_nova, localizacao_id or None, observacao)
        log_paiol(db, user, request, f"Ajuste de estoque — material #{material_id} → {quantidade_nova}")
        return RedirectResponse("/paiol/movimentacoes", status_code=HTTP_302_FOUND)
    except PaiolEstoqueError as e:
        return _render_form(request, db, user, TipoMovimentacaoPaiol.AJUSTE.value, str(e))


# ── Inventário ─────────────────────────────────────────────

@router.get("/inventario")
def inventario_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return _render_form(request, db, user, TipoMovimentacaoPaiol.INVENTARIO.value)


@router.post("/inventario")
def inventario_post(
    request: Request,
    material_id: int = Form(...),
    deposito_id: int = Form(...),
    localizacao_id: Optional[int] = Form(None),
    quantidade_nova: int = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    try:
        registrar_inventario(db, ctx, material_id, deposito_id, quantidade_nova, localizacao_id or None, observacao)
        log_paiol(db, user, request, f"Inventário — material #{material_id} → {quantidade_nova}")
        return RedirectResponse("/paiol/movimentacoes", status_code=HTTP_302_FOUND)
    except PaiolEstoqueError as e:
        return _render_form(request, db, user, TipoMovimentacaoPaiol.INVENTARIO.value, str(e))
