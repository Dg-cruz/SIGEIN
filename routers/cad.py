"""Central de Atendimento e Despacho (CAD)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from database import get_db
from dependencies import agora_brasilia, get_current_user, registrar_log
from models import CadOcorrencia, User
from services.cad_dashboard_service import (
    add_widget,
    build_cad_metrics,
    list_available_widgets,
    list_user_widgets,
    remove_widget,
)
from services.cad_ocorrencias_service import (
    buscar_endereco_cep,
    gerar_protocolo,
    parse_datetime_local,
)
from services.cad_opcoes_service import (
    TIPOS_OPCAO,
    TIPOS_OPCAO_LABELS,
    atualizar_opcao,
    catalogos_formulario,
    criar_opcao,
    excluir_opcao,
    listar_opcoes,
    resolver_natureza_db,
)
from templating import templates

router = APIRouter(prefix="/cad", tags=["CAD"])

_cad_schema_ready = False


def _ensure_cad_schema() -> None:
    """Garante tabelas CAD no DB (esp. Vercel, onde create_all completo fica off)."""
    global _cad_schema_ready
    if _cad_schema_ready:
        return
    try:
        from database import Base, engine
        from models import CadDashboardWidget, CadOcorrencia, CadOpcaoLista

        Base.metadata.create_all(
            bind=engine,
            tables=[
                CadOcorrencia.__table__,
                CadDashboardWidget.__table__,
                CadOpcaoLista.__table__,
            ],
        )
        _cad_schema_ready = True
    except Exception:
        pass


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


def _require_user(db: Session, user: str):
    if not user:
        return None, RedirectResponse("/login")
    u = _user_obj(db, user)
    if not u:
        return None, RedirectResponse("/login")
    if not u.municipio_id:
        return None, RedirectResponse("/dashboard")
    _ensure_cad_schema()
    return u, None


def _form_catalogs(db: Session, municipio_id: int) -> dict:
    return catalogos_formulario(db, municipio_id)


def _pick(codigo: str, pairs: list[tuple[str, str]], default: str) -> str:
    valid = {c for c, _ in pairs}
    return codigo if codigo in valid else default


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
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
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


def _ocorrencia_do_form(
    *,
    db: Session,
    u: User,
    catalogs: dict,
    protocolo: str | None,
    canal: str,
    prioridade: str,
    status: str,
    data_hora_fato: str | None,
    solicitante_nome: str | None,
    solicitante_telefone: str | None,
    solicitante_documento: str | None,
    solicitante_anonimo: str | None,
    tipo_natureza: str,
    natureza_codigo: str,
    meio_empregado: str,
    tentado: str | None,
    em_evento: str | None,
    evento_descricao: str | None,
    cep: str | None,
    logradouro: str | None,
    numero: str | None,
    complemento: str | None,
    bairro: str | None,
    cidade: str | None,
    uf: str | None,
    ponto_referencia: str | None,
    endereco_sem_cep: str | None,
    relato: str | None,
    observacao: str | None,
    existing: CadOcorrencia | None = None,
) -> CadOcorrencia:
    nat = resolver_natureza_db(db, u.municipio_id, natureza_codigo)
    tipo = _pick(tipo_natureza, catalogs["tipos_natureza"], nat["tipo"])
    agora = agora_brasilia()
    obj = existing or CadOcorrencia(
        protocolo=protocolo or "",
        municipio_id=u.municipio_id,
        orgao_id=u.orgao_id,
        unidade_id=u.unidade_id,
        created_by=u.id,
        data_hora_registro=agora,
    )
    obj.canal = _pick(canal, catalogs["canais"], catalogs["canais"][0][0] if catalogs["canais"] else "153")
    obj.prioridade = _pick(
        prioridade,
        catalogs["prioridades"],
        catalogs["prioridades"][0][0] if catalogs["prioridades"] else "rotina",
    )
    obj.status = _pick(
        status,
        catalogs["status_list"],
        catalogs["status_list"][0][0] if catalogs["status_list"] else "aberta",
    )
    obj.data_hora_fato = parse_datetime_local(data_hora_fato)
    anonimo = str(solicitante_anonimo or "").lower() in {"1", "on", "true", "sim"}
    obj.solicitante_anonimo = anonimo
    obj.solicitante_nome = None if anonimo else (solicitante_nome or "").strip() or None
    obj.solicitante_telefone = (solicitante_telefone or "").strip() or None
    obj.solicitante_documento = (
        None if anonimo else (solicitante_documento or "").strip() or None
    )
    obj.tipo_natureza = tipo
    obj.natureza_codigo = nat["codigo"]
    obj.natureza_nome = nat["nome"]
    obj.natureza_grupo = nat["grupo"]
    obj.meio_empregado = _pick(
        meio_empregado,
        catalogs["meios"],
        catalogs["meios"][0][0] if catalogs["meios"] else "nao_houve",
    )
    obj.tentado = str(tentado or "").lower() in {"1", "on", "true", "sim"}
    obj.em_evento = str(em_evento or "").lower() in {"1", "on", "true", "sim"}
    obj.evento_descricao = (evento_descricao or "").strip() or None if obj.em_evento else None
    obj.endereco_sem_cep = str(endereco_sem_cep or "").lower() in {"1", "on", "true", "sim"}
    obj.cep = (cep or "").strip() or None
    obj.logradouro = (logradouro or "").strip() or None
    obj.numero = (numero or "").strip() or None
    obj.complemento = (complemento or "").strip() or None
    obj.bairro = (bairro or "").strip() or None
    obj.cidade = (cidade or "").strip() or None
    obj.uf = ((uf or "").strip().upper()[:2] or None)
    obj.ponto_referencia = (ponto_referencia or "").strip() or None
    obj.relato = (relato or "").strip() or None
    obj.observacao = (observacao or "").strip() or None
    obj.updated_at = agora
    return obj


@router.get("/api/cep/{cep}")
def api_cep(cep: str, user: str = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "error": "Não autenticado."}, status_code=401)
    return JSONResponse(buscar_endereco_cep(cep))


@router.get("/api/dashboard/widgets")
def api_widgets(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return JSONResponse({"error": "Não autenticado."}, status_code=401)
    metrics = build_cad_metrics(db, u.municipio_id)
    return JSONResponse({"widgets": list_user_widgets(db, u.id, metrics)})


@router.get("/api/dashboard/widgets/disponiveis")
def api_widgets_disponiveis(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return JSONResponse({"error": "Não autenticado."}, status_code=401)
    return JSONResponse({"itens": list_available_widgets(db, u.id)})


@router.post("/api/dashboard/widgets")
async def api_widgets_add(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return JSONResponse({"error": "Não autenticado."}, status_code=401)
    body = await request.json()
    key = (body or {}).get("widget_key") or (body or {}).get("key")
    try:
        item = add_widget(db, u.id, key)
        metrics = build_cad_metrics(db, u.municipio_id)
        item["value"] = metrics.get(item["widget_key"], 0)
        return JSONResponse({"ok": True, "widget": item})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@router.delete("/api/dashboard/widgets/{widget_id}")
def api_widgets_remove(
    widget_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return JSONResponse({"error": "Não autenticado."}, status_code=401)
    ok = remove_widget(db, u.id, widget_id)
    if not ok:
        return JSONResponse({"ok": False, "error": "Widget não encontrado."}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("")
@router.get("/")
def cad_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    metrics = build_cad_metrics(db, u.municipio_id)
    widgets = list_user_widgets(db, u.id, metrics)
    catalogs = _form_catalogs(db, u.municipio_id)
    return templates.TemplateResponse(
        "cad/dashboard.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "cad_menu": CAD_MENU,
            "menu_key": "painel",
            "metrics": metrics,
            "widgets": widgets,
            "status_labels": catalogs["status_labels"],
            "prioridade_labels": catalogs["prioridade_labels"],
            "canal_labels": catalogs["canal_labels"],
        },
    )


@router.get("/ocorrencias")
def cad_ocorrencias(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    protocolo: str = Query(""),
    registro: str = Query(""),
    prioridade: str = Query(""),
    natureza: str = Query(""),
    local: str = Query(""),
    status: str = Query(""),
    atendente: str = Query(""),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect

    catalogs = _form_catalogs(db, u.municipio_id)
    query = (
        db.query(CadOcorrencia)
        .options(joinedload(CadOcorrencia.criador))
        .filter(CadOcorrencia.municipio_id == u.municipio_id)
    )

    if protocolo and protocolo.strip():
        query = query.filter(CadOcorrencia.protocolo.ilike(f"%{protocolo.strip()}%"))

    if registro and registro.strip():
        try:
            dia = datetime.strptime(registro.strip()[:10], "%Y-%m-%d")
            query = query.filter(
                CadOcorrencia.data_hora_registro >= dia,
                CadOcorrencia.data_hora_registro < dia + timedelta(days=1),
            )
        except ValueError:
            pass

    if prioridade and prioridade in catalogs["prioridade_labels"]:
        query = query.filter(CadOcorrencia.prioridade == prioridade)

    if natureza and natureza.strip():
        query = query.filter(CadOcorrencia.natureza_codigo == natureza.strip())

    if local and local.strip():
        termo_local = f"%{local.strip()}%"
        query = query.filter(
            (CadOcorrencia.logradouro.ilike(termo_local))
            | (CadOcorrencia.bairro.ilike(termo_local))
            | (CadOcorrencia.numero.ilike(termo_local))
            | (CadOcorrencia.cidade.ilike(termo_local))
        )

    if status and status in catalogs["status_labels"]:
        query = query.filter(CadOcorrencia.status == status)

    atendente_id = None
    if atendente and str(atendente).isdigit():
        atendente_id = int(atendente)
        query = query.filter(CadOcorrencia.created_by == atendente_id)

    ocorrencias = query.order_by(CadOcorrencia.data_hora_registro.desc()).limit(200).all()

    atendentes = (
        db.query(User.id, User.nome)
        .join(CadOcorrencia, CadOcorrencia.created_by == User.id)
        .filter(CadOcorrencia.municipio_id == u.municipio_id)
        .distinct()
        .order_by(User.nome)
        .all()
    )

    filtros_ativos = any(
        [
            (protocolo or "").strip(),
            (registro or "").strip(),
            prioridade,
            natureza,
            (local or "").strip(),
            status,
            atendente_id,
        ]
    )

    return templates.TemplateResponse(
        "cad/ocorrencias_list.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "cad_menu": CAD_MENU,
            "menu_key": "ocorrencias",
            "ocorrencias": ocorrencias,
            "filtros": {
                "protocolo": protocolo or "",
                "registro": registro or "",
                "prioridade": prioridade or "",
                "natureza": natureza or "",
                "local": local or "",
                "status": status or "",
                "atendente": str(atendente_id or ""),
            },
            "filtros_ativos": filtros_ativos,
            "atendentes": atendentes,
            **catalogs,
        },
    )


@router.get("/ocorrencias/nova")
def cad_ocorrencia_nova(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    agora = agora_brasilia()
    return templates.TemplateResponse(
        "cad/ocorrencias_form.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "cad_menu": CAD_MENU,
            "menu_key": "ocorrencias",
            "ocorrencia": None,
            "modo": "nova",
            "agora_valor": agora.strftime("%Y-%m-%dT%H:%M"),
            **_form_catalogs(db, u.municipio_id),
        },
    )


@router.post("/ocorrencias/nova")
async def cad_ocorrencia_criar(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    canal: str = Form("153"),
    prioridade: str = Form("rotina"),
    status: str = Form("aberta"),
    data_hora_fato: str = Form(None),
    solicitante_nome: str = Form(None),
    solicitante_telefone: str = Form(None),
    solicitante_documento: str = Form(None),
    solicitante_anonimo: str = Form(None),
    tipo_natureza: str = Form("atipica"),
    natureza_codigo: str = Form(...),
    meio_empregado: str = Form("nao_houve"),
    tentado: str = Form(None),
    em_evento: str = Form(None),
    evento_descricao: str = Form(None),
    cep: str = Form(None),
    logradouro: str = Form(None),
    numero: str = Form(None),
    complemento: str = Form(None),
    bairro: str = Form(None),
    cidade: str = Form(None),
    uf: str = Form(None),
    ponto_referencia: str = Form(None),
    endereco_sem_cep: str = Form(None),
    relato: str = Form(None),
    observacao: str = Form(None),
    enviar_despacho: str = Form(None),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect

    if enviar_despacho:
        status = "aguardando_despacho"

    catalogs = _form_catalogs(db, u.municipio_id)
    protocolo = gerar_protocolo(db)
    occ = _ocorrencia_do_form(
        db=db,
        u=u,
        catalogs=catalogs,
        protocolo=protocolo,
        canal=canal,
        prioridade=prioridade,
        status=status,
        data_hora_fato=data_hora_fato,
        solicitante_nome=solicitante_nome,
        solicitante_telefone=solicitante_telefone,
        solicitante_documento=solicitante_documento,
        solicitante_anonimo=solicitante_anonimo,
        tipo_natureza=tipo_natureza,
        natureza_codigo=natureza_codigo,
        meio_empregado=meio_empregado,
        tentado=tentado,
        em_evento=em_evento,
        evento_descricao=evento_descricao,
        cep=cep,
        logradouro=logradouro,
        numero=numero,
        complemento=complemento,
        bairro=bairro,
        cidade=cidade,
        uf=uf,
        ponto_referencia=ponto_referencia,
        endereco_sem_cep=endereco_sem_cep,
        relato=relato,
        observacao=observacao,
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)
    registrar_log(
        db,
        usuario=u.email,
        acao=f"CAD: registrou ocorrência {occ.protocolo}",
        request=request,
        tipo="operacional",
    )
    return RedirectResponse("/cad/ocorrencias", status_code=303)


@router.get("/ocorrencias/{ocorrencia_id}")
def cad_ocorrencia_detalhe(
    ocorrencia_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    occ = (
        db.query(CadOcorrencia)
        .options(joinedload(CadOcorrencia.criador))
        .filter(
            CadOcorrencia.id == ocorrencia_id,
            CadOcorrencia.municipio_id == u.municipio_id,
        )
        .first()
    )
    if not occ:
        return RedirectResponse("/cad/ocorrencias", status_code=303)
    return templates.TemplateResponse(
        "cad/ocorrencias_form.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "cad_menu": CAD_MENU,
            "menu_key": "ocorrencias",
            "ocorrencia": occ,
            "modo": "editar",
            "agora_valor": None,
            **_form_catalogs(db, u.municipio_id),
        },
    )


@router.post("/ocorrencias/{ocorrencia_id}")
async def cad_ocorrencia_atualizar(
    ocorrencia_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    canal: str = Form("153"),
    prioridade: str = Form("rotina"),
    status: str = Form("aberta"),
    data_hora_fato: str = Form(None),
    solicitante_nome: str = Form(None),
    solicitante_telefone: str = Form(None),
    solicitante_documento: str = Form(None),
    solicitante_anonimo: str = Form(None),
    tipo_natureza: str = Form("atipica"),
    natureza_codigo: str = Form(...),
    meio_empregado: str = Form("nao_houve"),
    tentado: str = Form(None),
    em_evento: str = Form(None),
    evento_descricao: str = Form(None),
    cep: str = Form(None),
    logradouro: str = Form(None),
    numero: str = Form(None),
    complemento: str = Form(None),
    bairro: str = Form(None),
    cidade: str = Form(None),
    uf: str = Form(None),
    ponto_referencia: str = Form(None),
    endereco_sem_cep: str = Form(None),
    relato: str = Form(None),
    observacao: str = Form(None),
    enviar_despacho: str = Form(None),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    occ = (
        db.query(CadOcorrencia)
        .filter(
            CadOcorrencia.id == ocorrencia_id,
            CadOcorrencia.municipio_id == u.municipio_id,
        )
        .first()
    )
    if not occ:
        return RedirectResponse("/cad/ocorrencias", status_code=303)
    if occ.status == "encerrada":
        return RedirectResponse(f"/cad/ocorrencias/{occ.id}?erro=encerrada", status_code=303)

    if enviar_despacho:
        status = "aguardando_despacho"

    catalogs = _form_catalogs(db, u.municipio_id)
    _ocorrencia_do_form(
        db=db,
        u=u,
        catalogs=catalogs,
        protocolo=occ.protocolo,
        canal=canal,
        prioridade=prioridade,
        status=status,
        data_hora_fato=data_hora_fato,
        solicitante_nome=solicitante_nome,
        solicitante_telefone=solicitante_telefone,
        solicitante_documento=solicitante_documento,
        solicitante_anonimo=solicitante_anonimo,
        tipo_natureza=tipo_natureza,
        natureza_codigo=natureza_codigo,
        meio_empregado=meio_empregado,
        tentado=tentado,
        em_evento=em_evento,
        evento_descricao=evento_descricao,
        cep=cep,
        logradouro=logradouro,
        numero=numero,
        complemento=complemento,
        bairro=bairro,
        cidade=cidade,
        uf=uf,
        ponto_referencia=ponto_referencia,
        endereco_sem_cep=endereco_sem_cep,
        relato=relato,
        observacao=observacao,
        existing=occ,
    )
    db.add(occ)
    db.commit()
    registrar_log(
        db,
        usuario=u.email,
        acao=f"CAD: atualizou ocorrência {occ.protocolo}",
        request=request,
        tipo="operacional",
    )
    return RedirectResponse("/cad/ocorrencias", status_code=303)


def _get_ocorrencia_municipio(db: Session, ocorrencia_id: int, municipio_id: int):
    return (
        db.query(CadOcorrencia)
        .filter(
            CadOcorrencia.id == ocorrencia_id,
            CadOcorrencia.municipio_id == municipio_id,
        )
        .first()
    )


@router.post("/ocorrencias/{ocorrencia_id}/enviar-despacho")
async def cad_ocorrencia_enviar_despacho(
    ocorrencia_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    occ = _get_ocorrencia_municipio(db, ocorrencia_id, u.municipio_id)
    if not occ:
        return RedirectResponse("/cad/ocorrencias", status_code=303)
    if occ.status in ("encerrada", "cancelada"):
        return RedirectResponse("/cad/ocorrencias", status_code=303)

    occ.status = "aguardando_despacho"
    occ.updated_at = agora_brasilia()
    db.add(occ)
    db.commit()
    registrar_log(
        db,
        usuario=u.email,
        acao=f"CAD: enviou ocorrência {occ.protocolo} ao despacho",
        request=request,
        tipo="operacional",
    )
    return RedirectResponse("/cad/ocorrencias", status_code=303)


@router.post("/ocorrencias/{ocorrencia_id}/encerrar")
async def cad_ocorrencia_encerrar(
    ocorrencia_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    occ = _get_ocorrencia_municipio(db, ocorrencia_id, u.municipio_id)
    if not occ:
        return RedirectResponse("/cad/ocorrencias", status_code=303)
    if occ.status == "encerrada":
        return RedirectResponse("/cad/ocorrencias", status_code=303)

    occ.status = "encerrada"
    occ.updated_at = agora_brasilia()
    db.add(occ)
    db.commit()
    registrar_log(
        db,
        usuario=u.email,
        acao=f"CAD: encerrou ocorrência {occ.protocolo}",
        request=request,
        tipo="operacional",
    )
    return RedirectResponse("/cad/ocorrencias", status_code=303)


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
    tipo: str = Query("canal"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=5, le=50),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    if tipo not in TIPOS_OPCAO_LABELS:
        tipo = "canal"
    if por_pagina not in (5, 10, 25, 50):
        por_pagina = 10
    opcoes_all = listar_opcoes(db, u.municipio_id, tipo, apenas_ativos=False)
    total = len(opcoes_all)
    ultima_pagina = max(1, (total + por_pagina - 1) // por_pagina)
    if pagina > ultima_pagina:
        pagina = ultima_pagina
    offset = (pagina - 1) * por_pagina
    opcoes = opcoes_all[offset : offset + por_pagina]
    return templates.TemplateResponse(
        "cad/configuracoes.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "cad_menu": CAD_MENU,
            "menu_key": "configuracoes",
            "tipos_opcao": TIPOS_OPCAO,
            "tipo_atual": tipo,
            "tipo_label": TIPOS_OPCAO_LABELS[tipo],
            "opcoes": opcoes,
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "ultima_pagina": ultima_pagina,
            "erro": request.query_params.get("erro"),
            "ok": request.query_params.get("ok"),
        },
    )


@router.post("/configuracoes/opcoes")
async def cad_configuracoes_criar(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    tipo: str = Form(...),
    label: str = Form(...),
    codigo: str = Form(""),
    extra1: str = Form(""),
    extra2: str = Form(""),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    try:
        criar_opcao(
            db,
            municipio_id=u.municipio_id,
            tipo=tipo,
            label=label,
            codigo=codigo or None,
            extra1=extra1 or None,
            extra2=extra2 or None,
        )
        registrar_log(
            db,
            usuario=u.email,
            acao=f"CAD: cadastrou opção '{label}' em {tipo}",
            request=request,
            tipo="operacional",
        )
        return RedirectResponse(
            f"/cad/configuracoes?tipo={tipo}&ok=1",
            status_code=303,
        )
    except ValueError as exc:
        from urllib.parse import quote

        return RedirectResponse(
            f"/cad/configuracoes?tipo={tipo}&erro={quote(str(exc))}",
            status_code=303,
        )


@router.post("/configuracoes/opcoes/{opcao_id}")
async def cad_configuracoes_atualizar(
    opcao_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    tipo: str = Form(...),
    label: str = Form(...),
    extra1: str = Form(""),
    extra2: str = Form(""),
    ativo: str = Form("1"),
    ordem: str = Form("0"),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    try:
        atualizar_opcao(
            db,
            municipio_id=u.municipio_id,
            opcao_id=opcao_id,
            label=label,
            extra1=extra1 or None,
            extra2=extra2 or None,
            ativo=str(ativo).lower() in {"1", "on", "true", "sim"},
            ordem=int(ordem or 0),
        )
        return RedirectResponse(
            f"/cad/configuracoes?tipo={tipo}&ok=1",
            status_code=303,
        )
    except ValueError as exc:
        from urllib.parse import quote

        return RedirectResponse(
            f"/cad/configuracoes?tipo={tipo}&erro={quote(str(exc))}",
            status_code=303,
        )


@router.post("/configuracoes/opcoes/{opcao_id}/excluir")
async def cad_configuracoes_excluir(
    opcao_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    tipo: str = Form("canal"),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    try:
        excluir_opcao(db, u.municipio_id, opcao_id)
        return RedirectResponse(
            f"/cad/configuracoes?tipo={tipo}&ok=1",
            status_code=303,
        )
    except ValueError as exc:
        from urllib.parse import quote

        return RedirectResponse(
            f"/cad/configuracoes?tipo={tipo}&erro={quote(str(exc))}",
            status_code=303,
        )
