"""Rotas de workflow (requisições, distribuições, devoluções, baixas, destruição)."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND

from database import get_db
from dependencies import get_current_user
from services.paiol_audit import log_paiol
from models import PaiolDeposito, PaiolMaterial, StatusUsuarioEnum, Unidade, User
from paiol_constants import (
    CAUTELA_ABAS_EQUIPAMENTO,
    STATUS_CAUTELA_LABELS_STR,
    STATUS_REQUISICAO_LABELS_STR,
    StatusRequisicaoPaiol,
    TIPO_MOVIMENTO_LABELS,
    TipoMovimentacaoPaiol,
)
from services.paiol_assinatura_service import assinaturas_documento
from services.paiol_helpers import user_context
from services.paiol_cautela_service import (
    PaiolCautelaError,
    atualizar_cautela,
    cautela_para_form,
    criar_cautela,
    dar_baixa_cautela,
    excluir_cautela,
    listar_cautelas,
    listar_equipamentos_categoria,
    listar_servidores_habilitados,
    matricula_servidor,
    obter_cautela,
    parse_itens_json,
    resumo_cautela,
)
from services.paiol_workflow_service import (
    PaiolWorkflowError,
    aprovar_requisicao,
    atender_requisicao,
    cancelar_requisicao,
    criar_requisicao,
    enviar_requisicao,
    get_requisicao,
    listar_movimentacoes_tipo,
    listar_requisicoes,
    rejeitar_requisicao,
    registrar_baixa,
    registrar_destruicao,
    registrar_devolucao,
    requisicoes_aprovadas,
    atualizar_requisicao,
)
from templating import templates

router = APIRouter(prefix="/paiol/movimentacoes", tags=["Paiol — Workflow"])


def _auth(user: str):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


def _parse_itens(material_ids: list[str], quantidades: list[str]) -> list[tuple[int, int]]:
    itens = []
    for mid, qtd in zip(material_ids, quantidades):
        if not mid:
            continue
        itens.append((int(mid), int(qtd or 0)))
    return itens


def _materiais_depositos_unidades(db: Session, ctx: dict):
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
    unidades = (
        db.query(Unidade)
        .filter(Unidade.orgao_id == ctx["orgao_id"], Unidade.ativo == True)
        .order_by(Unidade.nome)
        .all()
    )
    return materiais, depositos, unidades

# ── Requisições ────────────────────────────────────────────

@router.get("/requisicoes")
def requisicoes_lista(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    reqs = listar_requisicoes(db, ctx["orgao_id"])
    return templates.TemplateResponse(
        "paiol/requisicoes_list.html",
        {
            "request": request,
            "hide_app_header": True,
            "requisicoes": reqs,
            "status_labels": STATUS_REQUISICAO_LABELS_STR,
        },
    )


@router.get("/requisicoes/add")
def requisicao_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    materiais, depositos, unidades = _materiais_depositos_unidades(db, ctx)
    return templates.TemplateResponse(
        "paiol/forms/requisicao_form.html",
        {
            "request": request,
            "hide_app_header": True,
            "action": "add",
            "materiais": materiais,
            "depositos": depositos,
            "unidades": unidades,
            "item": None,
            "error": None,
        },
    )


@router.post("/requisicoes/add")
def requisicao_add_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    unidade_id: Optional[str] = Form(None),
    deposito_id: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
    material_id: list[str] = Form([]),
    quantidade: list[str] = Form([]),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        req = criar_requisicao(
            db,
            ctx,
            unidade_id=int(unidade_id) if unidade_id else None,
            deposito_id=int(deposito_id) if deposito_id else None,
            observacao=observacao,
            itens=_parse_itens(material_id, quantidade),
        )
        log_paiol(db, user, request, f"Requisição {req.numero} criada")
        return RedirectResponse(f"/paiol/movimentacoes/requisicoes/{req.id}", status_code=HTTP_302_FOUND)
    except (PaiolWorkflowError, ValueError) as e:
        materiais, depositos, unidades = _materiais_depositos_unidades(db, ctx)
        return templates.TemplateResponse(
            "paiol/forms/requisicao_form.html",
            {
                "request": request,
                "hide_app_header": True,
                "action": "add",
                "materiais": materiais,
                "depositos": depositos,
                "unidades": unidades,
                "item": None,
                "error": str(e),
            },
        )


@router.get("/requisicoes/edit/{req_id}")
def requisicao_edit_form(req_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        req = get_requisicao(db, req_id, ctx["orgao_id"])
    except PaiolWorkflowError as e:
        return RedirectResponse("/paiol/movimentacoes/requisicoes", status_code=HTTP_302_FOUND)
    materiais, depositos, unidades = _materiais_depositos_unidades(db, ctx)
    return templates.TemplateResponse(
        "paiol/forms/requisicao_form.html",
        {
            "request": request,
            "hide_app_header": True,
            "action": "edit",
            "materiais": materiais,
            "depositos": depositos,
            "unidades": unidades,
            "item": req,
            "error": None,
        },
    )


@router.post("/requisicoes/edit/{req_id}")
def requisicao_edit_post(
    req_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    unidade_id: Optional[str] = Form(None),
    deposito_id: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
    material_id: list[str] = Form([]),
    quantidade: list[str] = Form([]),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        atualizar_requisicao(
            db,
            ctx,
            req_id,
            unidade_id=int(unidade_id) if unidade_id else None,
            deposito_id=int(deposito_id) if deposito_id else None,
            observacao=observacao,
            itens=_parse_itens(material_id, quantidade),
        )
        log_paiol(db, user, request, f"Requisição #{req_id} atualizada")
        return RedirectResponse(f"/paiol/movimentacoes/requisicoes/{req_id}", status_code=HTTP_302_FOUND)
    except (PaiolWorkflowError, ValueError) as e:
        req = get_requisicao(db, req_id, ctx["orgao_id"])
        materiais, depositos, unidades = _materiais_depositos_unidades(db, ctx)
        return templates.TemplateResponse(
            "paiol/forms/requisicao_form.html",
            {
                "request": request,
                "hide_app_header": True,
                "action": "edit",
                "materiais": materiais,
                "depositos": depositos,
                "unidades": unidades,
                "item": req,
                "error": str(e),
            },
        )


@router.get("/requisicoes/{req_id}")
def requisicao_detalhe(req_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        req = get_requisicao(db, req_id, ctx["orgao_id"])
    except PaiolWorkflowError:
        return RedirectResponse("/paiol/movimentacoes/requisicoes", status_code=HTTP_302_FOUND)
    assinaturas = assinaturas_documento(db, "requisicao", req.id)
    return templates.TemplateResponse(
        "paiol/requisicao_detalhe.html",
        {
            "request": request,
            "hide_app_header": True,
            "req": req,
            "status_labels": STATUS_REQUISICAO_LABELS_STR,
            "assinaturas": assinaturas,
        },
    )


@router.post("/requisicoes/{req_id}/enviar")
def requisicao_enviar(req_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        enviar_requisicao(db, ctx, req_id)
        log_paiol(db, user, request, f"Requisição #{req_id} enviada para aprovação")
    except PaiolWorkflowError:
        pass
    return RedirectResponse(f"/paiol/movimentacoes/requisicoes/{req_id}", status_code=HTTP_302_FOUND)


@router.post("/requisicoes/{req_id}/aprovar")
def requisicao_aprovar(
    req_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    observacao: Optional[str] = Form(None),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        aprovar_requisicao(db, ctx, req_id, observacao)
        log_paiol(db, user, request, f"Requisição #{req_id} aprovada")
    except PaiolWorkflowError:
        pass
    return RedirectResponse(f"/paiol/movimentacoes/requisicoes/{req_id}", status_code=HTTP_302_FOUND)


@router.post("/requisicoes/{req_id}/rejeitar")
def requisicao_rejeitar(
    req_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    motivo: str = Form(...),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        rejeitar_requisicao(db, ctx, req_id, motivo)
        log_paiol(db, user, request, f"Requisição #{req_id} rejeitada")
    except PaiolWorkflowError:
        pass
    return RedirectResponse(f"/paiol/movimentacoes/requisicoes/{req_id}", status_code=HTTP_302_FOUND)


@router.post("/requisicoes/{req_id}/cancelar")
def requisicao_cancelar(req_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        cancelar_requisicao(db, ctx, req_id)
        log_paiol(db, user, request, f"Requisição #{req_id} cancelada")
    except PaiolWorkflowError:
        pass
    return RedirectResponse(f"/paiol/movimentacoes/requisicoes/{req_id}", status_code=HTTP_302_FOUND)


# ── Distribuições ──────────────────────────────────────────

@router.get("/distribuicoes")
def distribuicoes_lista(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    movs = listar_movimentacoes_tipo(db, ctx["orgao_id"], TipoMovimentacaoPaiol.DISTRIBUICAO.value)
    return templates.TemplateResponse(
        "paiol/operacoes_list.html",
        {
            "request": request,
            "hide_app_header": True,
            "titulo": "Distribuições",
            "subtitulo": "Atendimento de requisições aprovadas.",
            "icone": "fa-share-from-square",
            "add_url": "/paiol/movimentacoes/distribuicoes/add",
            "add_label": "Nova distribuição",
            "movimentacoes": movs,
            "tipos_mov": {TipoMovimentacaoPaiol.DISTRIBUICAO.value: TIPO_MOVIMENTO_LABELS[TipoMovimentacaoPaiol.DISTRIBUICAO]},
        },
    )


@router.get("/distribuicoes/add")
def distribuicao_add_form(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    req_id: Optional[int] = None,
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    _, depositos, _ = _materiais_depositos_unidades(db, ctx)
    reqs = requisicoes_aprovadas(db, ctx["orgao_id"])
    req_sel = None
    if req_id:
        try:
            req_sel = get_requisicao(db, req_id, ctx["orgao_id"])
        except PaiolWorkflowError:
            req_sel = None
    return templates.TemplateResponse(
        "paiol/forms/distribuicao_form.html",
        {
            "request": request,
            "hide_app_header": True,
            "requisicoes": reqs,
            "depositos": depositos,
            "req_sel": req_sel,
            "error": None,
        },
    )


@router.post("/distribuicoes/add")
def distribuicao_add_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    requisicao_id: int = Form(...),
    deposito_id: int = Form(...),
    observacao: Optional[str] = Form(None),
    item_id: list[str] = Form([]),
    quantidade: list[str] = Form([]),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    atend = [(int(i), int(q or 0)) for i, q in zip(item_id, quantidade) if i and int(q or 0) > 0]
    try:
        atender_requisicao(db, ctx, requisicao_id, deposito_id, atend, observacao)
        log_paiol(db, user, request, f"Distribuição da requisição #{requisicao_id}")
        return RedirectResponse("/paiol/movimentacoes/distribuicoes", status_code=HTTP_302_FOUND)
    except (PaiolWorkflowError, ValueError) as e:
        _, depositos, _ = _materiais_depositos_unidades(db, ctx)
        reqs = requisicoes_aprovadas(db, ctx["orgao_id"])
        req_sel = get_requisicao(db, requisicao_id, ctx["orgao_id"])
        return templates.TemplateResponse(
            "paiol/forms/distribuicao_form.html",
            {
                "request": request,
                "hide_app_header": True,
                "requisicoes": reqs,
                "depositos": depositos,
                "req_sel": req_sel,
                "error": str(e),
            },
        )


# ── Devoluções, baixas, destruição ─────────────────────────

def _operacao_list(tipo: TipoMovimentacaoPaiol, titulo, subtitulo, icone, add_url):
    def handler(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
        if redir := _auth(user):
            return redir
        ctx = user_context(db, user)
        movs = listar_movimentacoes_tipo(db, ctx["orgao_id"], tipo.value)
        return templates.TemplateResponse(
            "paiol/operacoes_list.html",
            {
                "request": request,
                "hide_app_header": True,
                "titulo": titulo,
                "subtitulo": subtitulo,
                "icone": icone,
                "add_url": add_url,
                "add_label": f"Registrar {titulo.lower().rstrip('ões').rstrip('s')}",
                "movimentacoes": movs,
                "tipos_mov": {tipo.value: TIPO_MOVIMENTO_LABELS[tipo]},
            },
        )
    return handler


@router.get("/cautela")
def cautela_lista(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    cautelas = listar_cautelas(db, ctx["orgao_id"])
    linhas = []
    for c in cautelas:
        resumo = resumo_cautela(c)
        linhas.append(
            {
                "cautela": c,
                "matricula": matricula_servidor(c.servidor),
                "resumo": resumo,
            }
        )
    return templates.TemplateResponse(
        "paiol/cautela_list.html",
        {
            "request": request,
            "hide_app_header": True,
            "cautelas": linhas,
            "status_labels": STATUS_CAUTELA_LABELS_STR,
        },
    )


def _render_cautela_form(request, ctx, db, *, cautela=None, error=None, form_data=None):
    servidores = listar_servidores_habilitados(db, ctx["orgao_id"])
    data = form_data or (cautela_para_form(cautela) if cautela else None)
    if data and data.get("servidor_id") and not data.get("servidor_nome"):
        srv = db.query(User).filter(User.id == data["servidor_id"]).first()
        if srv:
            data["servidor_nome"] = srv.nome
            data["servidor_matricula"] = matricula_servidor(srv)
    return templates.TemplateResponse(
        "paiol/cautela_form.html",
        {
            "request": request,
            "hide_app_header": True,
            "cautela": cautela,
            "form_data": data,
            "servidores": servidores,
            "abas_equipamento": CAUTELA_ABAS_EQUIPAMENTO,
            "status_labels": STATUS_CAUTELA_LABELS_STR,
            "error": error,
            "is_edit": cautela is not None,
        },
    )


@router.get("/cautela/api/servidores")
def cautela_api_servidores(
    q: str = Query(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    rows = listar_servidores_habilitados(db, ctx["orgao_id"], q)
    return JSONResponse(
        {
            "ok": True,
            "items": [
                {
                    "id": s.id,
                    "nome": s.nome,
                    "matricula": matricula_servidor(s),
                }
                for s in rows
            ],
        }
    )


@router.get("/cautela/api/equipamentos")
def cautela_api_equipamentos(
    categoria: str = Query(...),
    q: str = Query(""),
    cautela_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        itens = listar_equipamentos_categoria(
            db, ctx, categoria, q, exclude_cautela_id=cautela_id
        )
    except PaiolCautelaError as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=400)
    return JSONResponse({"ok": True, "items": itens})


@router.get("/cautela/add")
def cautela_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    return _render_cautela_form(request, ctx, db)


@router.post("/cautela/add")
def cautela_add_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    servidor_id: int = Form(...),
    itens_json: str = Form(...),
    observacao: str = Form(""),
    status: str = Form("ativa"),
    cautela_fixa: str = Form("nao"),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    is_fixa = (cautela_fixa or "").strip().lower() in {"sim", "1", "true", "on"}
    try:
        itens = parse_itens_json(itens_json)
        criar_cautela(db, ctx, servidor_id, itens, observacao, status, cautela_fixa=is_fixa)
        log_paiol(db, user, request, "Cautela registrada")
        return RedirectResponse("/paiol/movimentacoes/cautela", status_code=HTTP_302_FOUND)
    except (PaiolCautelaError, ValueError) as e:
        try:
            itens_parsed = parse_itens_json(itens_json)
        except PaiolCautelaError:
            itens_parsed = []
        form_data = {
            "servidor_id": servidor_id,
            "observacao": observacao,
            "status": status,
            "cautela_fixa": is_fixa,
            "itens": itens_parsed,
        }
        return _render_cautela_form(request, ctx, db, error=str(e), form_data=form_data)


@router.get("/cautela/edit/{cautela_id}")
def cautela_edit_form(
    cautela_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        cautela = obter_cautela(db, cautela_id, ctx["orgao_id"])
    except PaiolCautelaError as e:
        return RedirectResponse("/paiol/movimentacoes/cautela", status_code=HTTP_302_FOUND)
    return _render_cautela_form(request, ctx, db, cautela=cautela)


@router.post("/cautela/edit/{cautela_id}")
def cautela_edit_post(
    cautela_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    servidor_id: int = Form(...),
    itens_json: str = Form(...),
    observacao: str = Form(""),
    status: str = Form("ativa"),
    cautela_fixa: str = Form("nao"),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    is_fixa = (cautela_fixa or "").strip().lower() in {"sim", "1", "true", "on"}
    try:
        cautela = obter_cautela(db, cautela_id, ctx["orgao_id"])
        itens = parse_itens_json(itens_json)
        atualizar_cautela(
            db, ctx, cautela_id, servidor_id, itens, observacao, status, cautela_fixa=is_fixa
        )
        log_paiol(db, user, request, f"Cautela #{cautela_id} atualizada")
        return RedirectResponse("/paiol/movimentacoes/cautela", status_code=HTTP_302_FOUND)
    except (PaiolCautelaError, ValueError) as e:
        try:
            cautela = obter_cautela(db, cautela_id, ctx["orgao_id"])
        except PaiolCautelaError:
            return RedirectResponse("/paiol/movimentacoes/cautela", status_code=HTTP_302_FOUND)
        try:
            itens_parsed = parse_itens_json(itens_json)
        except PaiolCautelaError:
            itens_parsed = []
        form_data = {
            "servidor_id": servidor_id,
            "observacao": observacao,
            "status": status,
            "cautela_fixa": is_fixa,
            "itens": itens_parsed,
        }
        return _render_cautela_form(request, ctx, db, cautela=cautela, error=str(e), form_data=form_data)


@router.post("/cautela/delete/{cautela_id}")
def cautela_delete(
    cautela_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        excluir_cautela(db, ctx, cautela_id)
        log_paiol(db, user, request, f"Cautela #{cautela_id} excluída")
        return JSONResponse({"ok": True})
    except PaiolCautelaError as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=400)


@router.post("/cautela/baixa/{cautela_id}")
def cautela_baixa(
    cautela_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    try:
        dar_baixa_cautela(db, ctx, cautela_id)
        log_paiol(db, user, request, f"Baixa da cautela #{cautela_id}")
        return JSONResponse({"ok": True})
    except PaiolCautelaError as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=400)


@router.get("/devolucoes")
def devolucoes_lista(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    return _operacao_list(
        TipoMovimentacaoPaiol.DEVOLUCAO,
        "Devoluções",
        "Retorno de material ao paiol.",
        "fa-rotate-left",
        "/paiol/movimentacoes/devolucoes/add",
    )(request, db, user)


@router.get("/baixas")
def baixas_lista(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    return _operacao_list(
        TipoMovimentacaoPaiol.BAIXA,
        "Baixas",
        "Baixa patrimonial de material inservível.",
        "fa-ban",
        "/paiol/movimentacoes/baixas/add",
    )(request, db, user)


@router.get("/destruicao")
def destruicao_lista(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    return _operacao_list(
        TipoMovimentacaoPaiol.DESTRUICAO,
        "Destruição",
        "Processo de destruição com dupla custódia.",
        "fa-fire",
        "/paiol/movimentacoes/destruicao/add",
    )(request, db, user)


def _render_operacao_form(request, ctx, db, meta, error=None, **extra):
    materiais, depositos, _ = _materiais_depositos_unidades(db, ctx)
    return templates.TemplateResponse(
        "paiol/forms/operacao_workflow_form.html",
        {
            "request": request,
            "hide_app_header": True,
            "meta": meta,
            "materiais": materiais,
            "depositos": depositos,
            "error": error,
            **extra,
        },
    )


@router.get("/devolucoes/add")
def devolucao_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    return _render_operacao_form(
        request,
        ctx,
        db,
        {
            "titulo": "Devolução ao paiol",
            "action": "/paiol/movimentacoes/devolucoes/add",
            "submit": "Registrar devolução",
            "icone": "fa-rotate-left",
            "show_requisicao": True,
        },
    )


@router.post("/devolucoes/add")
def devolucao_add_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    material_id: int = Form(...),
    deposito_id: int = Form(...),
    quantidade: int = Form(...),
    observacao: str = Form(...),
    requisicao_id: Optional[str] = Form(None),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    meta = {"titulo": "Devolução ao paiol", "action": "/paiol/movimentacoes/devolucoes/add", "submit": "Registrar devolução", "icone": "fa-rotate-left", "show_requisicao": True}
    try:
        registrar_devolucao(
            db,
            ctx,
            material_id,
            deposito_id,
            quantidade,
            observacao,
            requisicao_id=int(requisicao_id) if requisicao_id else None,
        )
        log_paiol(db, user, request, "Devolução registrada")
        return RedirectResponse("/paiol/movimentacoes/devolucoes", status_code=HTTP_302_FOUND)
    except (PaiolWorkflowError, ValueError) as e:
        return _render_operacao_form(request, ctx, db, meta, str(e))


@router.get("/baixas/add")
def baixa_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    return _render_operacao_form(
        request,
        ctx,
        db,
        {"titulo": "Baixa patrimonial", "action": "/paiol/movimentacoes/baixas/add", "submit": "Registrar baixa", "icone": "fa-ban"},
    )


@router.post("/baixas/add")
def baixa_add_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    material_id: int = Form(...),
    deposito_id: int = Form(...),
    quantidade: int = Form(...),
    observacao: str = Form(...),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    meta = {"titulo": "Baixa patrimonial", "action": "/paiol/movimentacoes/baixas/add", "submit": "Registrar baixa", "icone": "fa-ban"}
    try:
        registrar_baixa(db, ctx, material_id, deposito_id, quantidade, observacao)
        log_paiol(db, user, request, "Baixa registrada")
        return RedirectResponse("/paiol/movimentacoes/baixas", status_code=HTTP_302_FOUND)
    except (PaiolWorkflowError, ValueError) as e:
        return _render_operacao_form(request, ctx, db, meta, str(e))


@router.get("/destruicao/add")
def destruicao_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    conferentes = (
        db.query(User)
        .filter(User.orgao_id == ctx["orgao_id"], User.id != ctx["user_id"], User.status == StatusUsuarioEnum.ATIVO.value)
        .order_by(User.nome)
        .all()
    )
    return _render_operacao_form(
        request,
        ctx,
        db,
        {
            "titulo": "Destruição de material",
            "action": "/paiol/movimentacoes/destruicao/add",
            "submit": "Registrar destruição",
            "icone": "fa-fire",
            "show_conferente": True,
        },
        conferentes=conferentes,
    )


@router.post("/destruicao/add")
def destruicao_add_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    material_id: int = Form(...),
    deposito_id: int = Form(...),
    quantidade: int = Form(...),
    observacao: str = Form(...),
    conferente_id: int = Form(...),
):
    if redir := _auth(user):
        return redir
    ctx = user_context(db, user)
    meta = {
        "titulo": "Destruição de material",
        "action": "/paiol/movimentacoes/destruicao/add",
        "submit": "Registrar destruição",
        "icone": "fa-fire",
        "show_conferente": True,
    }
    conferentes = (
        db.query(User)
        .filter(User.orgao_id == ctx["orgao_id"], User.id != ctx["user_id"], User.status == StatusUsuarioEnum.ATIVO.value)
        .order_by(User.nome)
        .all()
    )
    try:
        registrar_destruicao(db, ctx, material_id, deposito_id, quantidade, observacao, conferente_id)
        log_paiol(db, user, request, "Destruição registrada")
        return RedirectResponse("/paiol/movimentacoes/destruicao", status_code=HTTP_302_FOUND)
    except (PaiolWorkflowError, ValueError) as e:
        return _render_operacao_form(request, ctx, db, meta, str(e), conferentes=conferentes)
