"""Gestão de Frota."""

import re

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from database import get_db
from dependencies import get_current_user, registrar_log
from models import FrotaAtivo, Orgao, Unidade, User
from templating import templates

router = APIRouter(prefix="/frota", tags=["Gestão de Frota"])

_frota_schema_ready = False

ATIVO_TIPOS = (
    ("automovel", "Automóvel"),
    ("viatura", "Viatura"),
    ("motocicleta", "Motocicleta"),
    ("utilitario", "Utilitário"),
    ("caminhao", "Caminhão"),
    ("onibus", "Ônibus"),
    ("outro", "Outro"),
)

ATIVO_STATUS = (
    ("ativo", "Ativo"),
    ("em_manutencao", "Em manutenção"),
    ("inativo", "Inativo"),
    ("baixado", "Baixado"),
)

ATIVO_MARCAS = (
    ("chevrolet", "Chevrolet"),
    ("fiat", "Fiat"),
    ("ford", "Ford"),
    ("honda", "Honda"),
    ("hyundai", "Hyundai"),
    ("jeep", "Jeep"),
    ("mitsubishi", "Mitsubishi"),
    ("nissan", "Nissan"),
    ("toyota", "Toyota"),
    ("volkswagen", "Volkswagen"),
    ("yamaha", "Yamaha"),
    ("outra", "Outra"),
)

# (codigo, label, marca)
ATIVO_MODELOS = (
    ("onix", "Onix", "chevrolet"),
    ("s10", "S10", "chevrolet"),
    ("spin", "Spin", "chevrolet"),
    ("argo", "Argo", "fiat"),
    ("strada", "Strada", "fiat"),
    ("toro", "Toro", "fiat"),
    ("ranger", "Ranger", "ford"),
    ("ka", "Ka", "ford"),
    ("cg160", "CG 160", "honda"),
    ("civic", "Civic", "honda"),
    ("hrv", "HR-V", "honda"),
    ("hb20", "HB20", "hyundai"),
    ("creta", "Creta", "hyundai"),
    ("compass", "Compass", "jeep"),
    ("renegade", "Renegade", "jeep"),
    ("l200", "L200 Triton", "mitsubishi"),
    ("frontier", "Frontier", "nissan"),
    ("corolla", "Corolla", "toyota"),
    ("hilux", "Hilux", "toyota"),
    ("gol", "Gol", "volkswagen"),
    ("saveiro", "Saveiro", "volkswagen"),
    ("factor", "Factor", "yamaha"),
    ("outro", "Outro", "outra"),
)

ATIVO_CORES = (
    ("branca", "Branca"),
    ("preta", "Preta"),
    ("prata", "Prata"),
    ("cinza", "Cinza"),
    ("vermelha", "Vermelha"),
    ("azul", "Azul"),
    ("verde", "Verde"),
    ("amarela", "Amarela"),
    ("bege", "Bege"),
    ("outra", "Outra"),
)

ATIVO_TIPO_LABELS = dict(ATIVO_TIPOS)
ATIVO_STATUS_LABELS = dict(ATIVO_STATUS)
ATIVO_MARCA_LABELS = dict(ATIVO_MARCAS)
ATIVO_MODELO_LABELS = {c: l for c, l, _ in ATIVO_MODELOS}
ATIVO_COR_LABELS = dict(ATIVO_CORES)

FROTA_MENU = (
    {
        "key": "cadastro_ativo",
        "label": "Cadastro de Ativo",
        "subtitle": "Veículos e equipamentos da frota",
        "icon": "fa-car",
        "url": "/frota/cadastro-ativo",
    },
    {
        "key": "checklist_vistoria",
        "label": "Checklist e Vistoria",
        "subtitle": "Inspeções e checklists operacionais",
        "icon": "fa-clipboard-check",
        "url": "/frota/checklist-vistoria",
    },
    {
        "key": "configuracoes",
        "label": "Configurações",
        "subtitle": "Parâmetros e tipos do módulo",
        "icon": "fa-gear",
        "url": "/frota/configuracoes",
    },
    {
        "key": "multas_infracoes",
        "label": "Controle de Multas e Infrações",
        "subtitle": "Registro e acompanhamento de autuações",
        "icon": "fa-file-invoice",
        "url": "/frota/multas-infracoes",
    },
    {
        "key": "historico_ocorrencias",
        "label": "Histórico de Ocorrências",
        "subtitle": "Eventos e incidentes da frota",
        "icon": "fa-clock-rotate-left",
        "url": "/frota/historico-ocorrencias",
    },
    {
        "key": "manutencao",
        "label": "Manutenção",
        "subtitle": "Preventiva, corretiva e agenda",
        "icon": "fa-wrench",
        "url": "/frota/manutencao",
    },
)


def _ensure_frota_schema() -> None:
    global _frota_schema_ready
    if _frota_schema_ready:
        return
    try:
        from database import Base, engine

        Base.metadata.create_all(bind=engine, tables=[FrotaAtivo.__table__])
        _frota_schema_ready = True
    except Exception:
        pass


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
    _ensure_frota_schema()
    return u, None


def _unidades_municipio(db: Session, municipio_id: int) -> list[Unidade]:
    return (
        db.query(Unidade)
        .join(Orgao, Unidade.orgao_id == Orgao.id)
        .filter(Orgao.municipio_id == municipio_id, Unidade.ativo == True)
        .order_by(Unidade.nome)
        .all()
    )


def _norm_placa(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (value or "").strip()).upper()


def _format_placa(value: str) -> str:
    """Normaliza e aplica máscara AAA-9999 (antiga) ou AAA9A99 (Mercosul)."""
    raw = _norm_placa(value)
    if not raw:
        return ""
    if re.fullmatch(r"[A-Z]{3}\d{4}", raw):
        return f"{raw[:3]}-{raw[3:]}"
    return raw[:7]


def _placa_duplicada(
    db: Session,
    municipio_id: int,
    placa: str,
    *,
    excluir_id: int | None = None,
) -> bool:
    chave = _norm_placa(placa)
    if not chave:
        return False
    query = db.query(FrotaAtivo).filter(FrotaAtivo.municipio_id == municipio_id)
    if excluir_id is not None:
        query = query.filter(FrotaAtivo.id != excluir_id)
    return any(_norm_placa(a.placa) == chave for a in query.all())


def _valid_ano_modelo(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}/\d{4}", (value or "").strip()))


def _pick(codigo: str, pairs: tuple[tuple[str, str], ...], default: str = "") -> str:
    valid = {c for c, _ in pairs}
    if codigo in valid:
        return codigo
    return default or (pairs[0][0] if pairs else "")


def _render_pagina(
    request: Request,
    db: Session,
    user: str,
    *,
    titulo: str,
    descricao: str,
    menu_key: str,
    template: str = "frota/pagina.html",
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
            "frota_menu": FROTA_MENU,
        },
    )


@router.get("")
@router.get("/")
def frota_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "frota/dashboard.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "frota_menu": FROTA_MENU,
        },
    )


@router.get("/cadastro-ativo")
def frota_cadastro_ativo(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    placa: str = Query(""),
    tipo: str = Query(""),
    marca: str = Query(""),
    unidade: str = Query(""),
    ano: str = Query(""),
    status: str = Query(""),
    prefixo: str = Query(""),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect

    unidades = _unidades_municipio(db, u.municipio_id)
    unidades_filtro = [(un.id, un.nome) for un in unidades]

    query = (
        db.query(FrotaAtivo)
        .options(joinedload(FrotaAtivo.unidade))
        .filter(FrotaAtivo.municipio_id == u.municipio_id)
    )

    if placa and placa.strip():
        termo = _norm_placa(placa)
        query = query.filter(
            FrotaAtivo.placa.ilike(f"%{termo}%")
            | FrotaAtivo.placa.ilike(f"%{_format_placa(placa)}%")
        )
    if tipo and tipo in ATIVO_TIPO_LABELS:
        query = query.filter(FrotaAtivo.tipo_veiculo == tipo)
    if marca and marca.strip():
        termo = f"%{marca.strip()}%"
        query = query.filter(
            (FrotaAtivo.marca.ilike(termo)) | (FrotaAtivo.modelo.ilike(termo))
        )
    if unidade and str(unidade).isdigit():
        query = query.filter(FrotaAtivo.unidade_id == int(unidade))
    if ano and ano.strip():
        query = query.filter(FrotaAtivo.ano_modelo.ilike(f"%{ano.strip()}%"))
    if status and status in ATIVO_STATUS_LABELS:
        query = query.filter(FrotaAtivo.status == status)
    if prefixo and prefixo.strip():
        query = query.filter(FrotaAtivo.numero_frota.ilike(f"%{prefixo.strip()}%"))

    ativos = query.order_by(FrotaAtivo.placa.asc()).limit(500).all()

    # Corrige placas antigas sem máscara (ex.: JQZ4816 → JQZ-4816)
    placa_corrigida = False
    for a in ativos:
        fmt = _format_placa(a.placa)
        if fmt and a.placa != fmt:
            a.placa = fmt
            placa_corrigida = True
    if placa_corrigida:
        db.commit()

    filtros_ativos = any(
        [
            (placa or "").strip(),
            tipo,
            (marca or "").strip(),
            (unidade or "").strip(),
            (ano or "").strip(),
            status,
            (prefixo or "").strip(),
        ]
    )

    return templates.TemplateResponse(
        "frota/ativos_list.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "frota_menu": FROTA_MENU,
            "menu_key": "cadastro_ativo",
            "ativos": ativos,
            "tipos": ATIVO_TIPOS,
            "status_list": ATIVO_STATUS,
            "tipo_labels": ATIVO_TIPO_LABELS,
            "status_labels": ATIVO_STATUS_LABELS,
            "marca_labels": ATIVO_MARCA_LABELS,
            "modelo_labels": ATIVO_MODELO_LABELS,
            "cor_labels": ATIVO_COR_LABELS,
            "unidades": unidades_filtro,
            "filtros": {
                "placa": placa or "",
                "tipo": tipo or "",
                "marca": marca or "",
                "unidade": unidade or "",
                "ano": ano or "",
                "status": status or "",
                "prefixo": prefixo or "",
            },
            "filtros_ativos": filtros_ativos,
            "format_placa": _format_placa,
        },
    )


def _form_vazio(**overrides) -> dict:
    base = {
        "numero_frota": "",
        "placa": "",
        "chassi": "",
        "renavam": "",
        "ano_modelo": "",
        "unidade_id": "",
        "marca": "",
        "modelo": "",
        "tipo_veiculo": "",
        "cor": "",
    }
    base.update(overrides)
    return base


def _contexto_formulario(
    u: User,
    db: Session,
    *,
    form: dict,
    form_erro: str = "",
    ativo: FrotaAtivo | None = None,
):
    return {
        "user_obj": u,
        "frota_menu": FROTA_MENU,
        "menu_key": "cadastro_ativo",
        "unidades_form": _unidades_municipio(db, u.municipio_id),
        "tipos": ATIVO_TIPOS,
        "marcas": ATIVO_MARCAS,
        "modelos": ATIVO_MODELOS,
        "cores": ATIVO_CORES,
        "form": form,
        "form_erro": form_erro,
        "ativo": ativo,
        "is_edit": ativo is not None,
    }


def _form_from_ativo(ativo: FrotaAtivo) -> dict:
    return _form_vazio(
        numero_frota=ativo.numero_frota or "",
        placa=_format_placa(ativo.placa),
        chassi=ativo.chassi or "",
        renavam=ativo.renavam or "",
        ano_modelo=ativo.ano_modelo or "",
        unidade_id=str(ativo.unidade_id or ""),
        marca=ativo.marca or "",
        modelo=ativo.modelo or "",
        tipo_veiculo=ativo.tipo_veiculo or "",
        cor=ativo.cor or "",
    )


def _aplicar_campos_ativo(
    *,
    ativo: FrotaAtivo,
    u: User,
    unidade: Unidade,
    numero_frota: str,
    chassi: str,
    renavam: str,
    placa_fmt: str,
    ano_n: str,
    marca_n: str,
    modelo_n: str,
    tipo_n: str,
    cor_n: str,
) -> None:
    ativo.municipio_id = u.municipio_id
    ativo.orgao_id = u.orgao_id or unidade.orgao_id
    ativo.unidade_id = unidade.id
    ativo.numero_frota = (numero_frota or "").strip()[:40]
    ativo.chassi = (chassi or "").strip().upper()[:40]
    ativo.renavam = re.sub(r"\D", "", (renavam or "").strip())[:20]
    ativo.placa = placa_fmt[:10]
    ativo.ano_modelo = ano_n
    ativo.marca = marca_n
    ativo.modelo = modelo_n
    ativo.tipo_veiculo = tipo_n
    ativo.cor = cor_n


def _validar_form_ativo(
    *,
    db: Session,
    u: User,
    numero_frota: str,
    chassi: str,
    renavam: str,
    placa: str,
    ano_modelo: str,
    unidade_id: str,
    marca: str,
    modelo: str,
    tipo_veiculo: str,
    cor: str,
    excluir_id: int | None = None,
):
    placa_fmt = _format_placa(placa)
    ano_n = (ano_modelo or "").strip()
    unidades = {un.id: un for un in _unidades_municipio(db, u.municipio_id)}
    unidade_ok = unidade_id.isdigit() and int(unidade_id) in unidades

    if not (numero_frota or "").strip() or not (chassi or "").strip() or not (renavam or "").strip():
        return None, "obrigatorios"
    if not placa_fmt or not _valid_ano_modelo(ano_n):
        return None, "formato"
    if not unidade_ok:
        return None, "unidade"
    if _placa_duplicada(db, u.municipio_id, placa_fmt, excluir_id=excluir_id):
        return None, "placa"

    unidade_id_int = int(unidade_id)
    marca_n = _pick(marca, ATIVO_MARCAS)
    tipo_n = _pick(tipo_veiculo, ATIVO_TIPOS)
    cor_n = _pick(cor, ATIVO_CORES)
    modelos_validos = {c for c, _, m in ATIVO_MODELOS if m == marca_n or c == "outro"}
    modelo_n = modelo if modelo in modelos_validos or modelo in ATIVO_MODELO_LABELS else "outro"

    return {
        "unidade": unidades[unidade_id_int],
        "placa_fmt": placa_fmt,
        "ano_n": ano_n,
        "marca_n": marca_n,
        "modelo_n": modelo_n,
        "tipo_n": tipo_n,
        "cor_n": cor_n,
    }, None


@router.get("/cadastro-ativo/novo")
def frota_cadastro_ativo_novo(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "frota/ativos_form.html",
        {
            "request": request,
            "user": user,
            **_contexto_formulario(u, db, form=_form_vazio(), form_erro=""),
        },
    )


@router.post("/cadastro-ativo/novo")
def frota_cadastro_ativo_criar(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    numero_frota: str = Form(""),
    chassi: str = Form(""),
    renavam: str = Form(""),
    placa: str = Form(""),
    ano_modelo: str = Form(""),
    unidade_id: str = Form(""),
    marca: str = Form(""),
    modelo: str = Form(""),
    tipo_veiculo: str = Form(""),
    cor: str = Form(""),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect

    form_vals = _form_vazio(
        numero_frota=numero_frota or "",
        placa=_format_placa(placa) or (placa or ""),
        chassi=chassi or "",
        renavam=renavam or "",
        ano_modelo=ano_modelo or "",
        unidade_id=unidade_id or "",
        marca=marca or "",
        modelo=modelo or "",
        tipo_veiculo=tipo_veiculo or "",
        cor=cor or "",
    )

    def _reexibir(erro: str):
        return templates.TemplateResponse(
            "frota/ativos_form.html",
            {
                "request": request,
                "user": user,
                **_contexto_formulario(u, db, form=form_vals, form_erro=erro),
            },
            status_code=400,
        )

    dados, erro = _validar_form_ativo(
        db=db,
        u=u,
        numero_frota=numero_frota,
        chassi=chassi,
        renavam=renavam,
        placa=placa,
        ano_modelo=ano_modelo,
        unidade_id=unidade_id,
        marca=marca,
        modelo=modelo,
        tipo_veiculo=tipo_veiculo,
        cor=cor,
    )
    if erro:
        return _reexibir(erro)

    ativo = FrotaAtivo(status="ativo", created_by=u.id)
    _aplicar_campos_ativo(
        ativo=ativo,
        u=u,
        unidade=dados["unidade"],
        numero_frota=numero_frota,
        chassi=chassi,
        renavam=renavam,
        placa_fmt=dados["placa_fmt"],
        ano_n=dados["ano_n"],
        marca_n=dados["marca_n"],
        modelo_n=dados["modelo_n"],
        tipo_n=dados["tipo_n"],
        cor_n=dados["cor_n"],
    )
    db.add(ativo)
    db.commit()
    registrar_log(
        db,
        user,
        f"Cadastrou ativo de frota {ativo.placa} (n.º {ativo.numero_frota})",
        user_id=u.id,
        request=request,
    )
    return RedirectResponse("/frota/cadastro-ativo", status_code=303)


@router.get("/cadastro-ativo/{ativo_id}")
def frota_cadastro_ativo_editar(
    ativo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect

    ativo = (
        db.query(FrotaAtivo)
        .filter(FrotaAtivo.id == ativo_id, FrotaAtivo.municipio_id == u.municipio_id)
        .first()
    )
    if not ativo:
        return RedirectResponse("/frota/cadastro-ativo", status_code=303)

    return templates.TemplateResponse(
        "frota/ativos_form.html",
        {
            "request": request,
            "user": user,
            **_contexto_formulario(u, db, form=_form_from_ativo(ativo), ativo=ativo),
        },
    )


@router.post("/cadastro-ativo/{ativo_id}")
def frota_cadastro_ativo_atualizar(
    ativo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    numero_frota: str = Form(""),
    chassi: str = Form(""),
    renavam: str = Form(""),
    placa: str = Form(""),
    ano_modelo: str = Form(""),
    unidade_id: str = Form(""),
    marca: str = Form(""),
    modelo: str = Form(""),
    tipo_veiculo: str = Form(""),
    cor: str = Form(""),
):
    u, redirect = _require_user(db, user)
    if redirect:
        return redirect

    ativo = (
        db.query(FrotaAtivo)
        .filter(FrotaAtivo.id == ativo_id, FrotaAtivo.municipio_id == u.municipio_id)
        .first()
    )
    if not ativo:
        return RedirectResponse("/frota/cadastro-ativo", status_code=303)

    form_vals = _form_vazio(
        numero_frota=numero_frota or "",
        placa=_format_placa(placa) or (placa or ""),
        chassi=chassi or "",
        renavam=renavam or "",
        ano_modelo=ano_modelo or "",
        unidade_id=unidade_id or "",
        marca=marca or "",
        modelo=modelo or "",
        tipo_veiculo=tipo_veiculo or "",
        cor=cor or "",
    )

    def _reexibir(erro: str):
        return templates.TemplateResponse(
            "frota/ativos_form.html",
            {
                "request": request,
                "user": user,
                **_contexto_formulario(u, db, form=form_vals, form_erro=erro, ativo=ativo),
            },
            status_code=400,
        )

    dados, erro = _validar_form_ativo(
        db=db,
        u=u,
        numero_frota=numero_frota,
        chassi=chassi,
        renavam=renavam,
        placa=placa,
        ano_modelo=ano_modelo,
        unidade_id=unidade_id,
        marca=marca,
        modelo=modelo,
        tipo_veiculo=tipo_veiculo,
        cor=cor,
        excluir_id=ativo.id,
    )
    if erro:
        return _reexibir(erro)

    _aplicar_campos_ativo(
        ativo=ativo,
        u=u,
        unidade=dados["unidade"],
        numero_frota=numero_frota,
        chassi=chassi,
        renavam=renavam,
        placa_fmt=dados["placa_fmt"],
        ano_n=dados["ano_n"],
        marca_n=dados["marca_n"],
        modelo_n=dados["modelo_n"],
        tipo_n=dados["tipo_n"],
        cor_n=dados["cor_n"],
    )
    db.commit()
    registrar_log(
        db,
        user,
        f"Atualizou ativo de frota {ativo.placa} (n.º {ativo.numero_frota})",
        user_id=u.id,
        request=request,
    )
    return RedirectResponse("/frota/cadastro-ativo", status_code=303)


@router.get("/checklist-vistoria")
def frota_checklist_vistoria(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Checklist e Vistoria",
        descricao="Checklists de uso e vistorias periódicas dos ativos.",
        menu_key="checklist_vistoria",
    )


@router.get("/configuracoes")
def frota_configuracoes(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Configurações",
        descricao="Parâmetros, tipos e regras do módulo Gestão de Frota.",
        menu_key="configuracoes",
    )


@router.get("/multas-infracoes")
def frota_multas_infracoes(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Controle de Multas e Infrações",
        descricao="Registro, acompanhamento e baixa de multas e infrações.",
        menu_key="multas_infracoes",
    )


@router.get("/historico-ocorrencias")
def frota_historico_ocorrencias(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Histórico de Ocorrências",
        descricao="Linha do tempo de eventos e incidentes relacionados à frota.",
        menu_key="historico_ocorrencias",
    )


@router.get("/manutencao")
def frota_manutencao(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return _render_pagina(
        request,
        db,
        user,
        titulo="Manutenção",
        descricao="Agendamento e controle de manutenções preventivas e corretivas.",
        menu_key="manutencao",
    )
