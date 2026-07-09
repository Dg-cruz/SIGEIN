from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND

from database import get_db
from dependencies import get_current_user
from services.paiol_audit import log_paiol
from models import (
    PaiolClasseMaterial,
    PaiolDeposito,
    PaiolFabricante,
    PaiolFornecedor,
    PaiolLocalizacao,
    PaiolMaterial,
    PaiolUsuarioAutorizado,
    Unidade,
    User,
)
from paiol_constants import TIPO_MATERIAL_LABELS, material_list_url
from services.paiol_helpers import user_context
from templating import templates

router = APIRouter(prefix="/paiol/cadastro", tags=["Paiol — Cadastro"])


def _redirect_login(user: str):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


def _form_ctx(request: Request, **extra):
    return {"request": request, "hide_app_header": True, **extra}


# ── Classes ────────────────────────────────────────────────

@router.get("/classes/add")
def classe_add_form(request: Request, user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return templates.TemplateResponse("paiol/forms/classe_form.html", _form_ctx(request, action="add"))


@router.post("/classes/add")
def classe_add(
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    descricao: str = Form(""),
    grupo_compatibilidade: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    db.add(
        PaiolClasseMaterial(
            codigo=codigo.strip().upper(),
            nome=nome.strip(),
            descricao=descricao.strip() or None,
            grupo_compatibilidade=grupo_compatibilidade.strip() or None,
        )
    )
    db.commit()
    log_paiol(db, user, request, f"Cadastrou classe {nome.strip()}")
    return RedirectResponse("/paiol/cadastro/classes", status_code=HTTP_302_FOUND)


@router.get("/classes/edit/{item_id}")
def classe_edit_form(item_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolClasseMaterial).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/classes", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("paiol/forms/classe_form.html", _form_ctx(request, action="edit", item=item))


@router.post("/classes/edit/{item_id}")
def classe_edit(
    item_id: int,
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    descricao: str = Form(""),
    grupo_compatibilidade: str = Form(""),
    ativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolClasseMaterial).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/classes", status_code=HTTP_302_FOUND)
    item.codigo = codigo.strip().upper()
    item.nome = nome.strip()
    item.descricao = descricao.strip() or None
    item.grupo_compatibilidade = grupo_compatibilidade.strip() or None
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou classe {nome.strip()} (ID {item_id})")
    return RedirectResponse("/paiol/cadastro/classes", status_code=HTTP_302_FOUND)


# ── Fabricantes ────────────────────────────────────────────

@router.get("/fabricantes/add")
def fabricante_add_form(request: Request, user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return templates.TemplateResponse("paiol/forms/fabricante_form.html", _form_ctx(request, action="add"))


@router.post("/fabricantes/add")
def fabricante_add(
    request: Request,
    nome: str = Form(...),
    pais: str = Form(""),
    cnpj: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    db.add(PaiolFabricante(nome=nome.strip(), pais=pais.strip() or None, cnpj=cnpj.strip() or None))
    db.commit()
    log_paiol(db, user, request, f"Cadastrou fabricante {nome.strip()}")
    return RedirectResponse("/paiol/cadastro/fabricantes", status_code=HTTP_302_FOUND)


@router.get("/fabricantes/edit/{item_id}")
def fabricante_edit_form(item_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolFabricante).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/fabricantes", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("paiol/forms/fabricante_form.html", _form_ctx(request, action="edit", item=item))


@router.post("/fabricantes/edit/{item_id}")
def fabricante_edit(
    item_id: int,
    request: Request,
    nome: str = Form(...),
    pais: str = Form(""),
    cnpj: str = Form(""),
    ativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolFabricante).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/fabricantes", status_code=HTTP_302_FOUND)
    item.nome = nome.strip()
    item.pais = pais.strip() or None
    item.cnpj = cnpj.strip() or None
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou fabricante {nome.strip()} (ID {item_id})")
    return RedirectResponse("/paiol/cadastro/fabricantes", status_code=HTTP_302_FOUND)


# ── Fornecedores ───────────────────────────────────────────

@router.get("/fornecedores/add")
def fornecedor_add_form(request: Request, user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return templates.TemplateResponse("paiol/forms/fornecedor_form.html", _form_ctx(request, action="add"))


@router.post("/fornecedores/add")
def fornecedor_add(
    request: Request,
    nome: str = Form(...),
    cnpj: str = Form(""),
    contato: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    db.add(PaiolFornecedor(nome=nome.strip(), cnpj=cnpj.strip() or None, contato=contato.strip() or None))
    db.commit()
    log_paiol(db, user, request, f"Cadastrou fornecedor {nome.strip()}")
    return RedirectResponse("/paiol/cadastro/fornecedores", status_code=HTTP_302_FOUND)


@router.get("/fornecedores/edit/{item_id}")
def fornecedor_edit_form(item_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolFornecedor).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/fornecedores", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("paiol/forms/fornecedor_form.html", _form_ctx(request, action="edit", item=item))


@router.post("/fornecedores/edit/{item_id}")
def fornecedor_edit(
    item_id: int,
    request: Request,
    nome: str = Form(...),
    cnpj: str = Form(""),
    contato: str = Form(""),
    ativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolFornecedor).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/fornecedores", status_code=HTTP_302_FOUND)
    item.nome = nome.strip()
    item.cnpj = cnpj.strip() or None
    item.contato = contato.strip() or None
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou fornecedor {nome.strip()} (ID {item_id})")
    return RedirectResponse("/paiol/cadastro/fornecedores", status_code=HTTP_302_FOUND)


# ── Depósitos ──────────────────────────────────────────────

@router.get("/depositos/add")
def deposito_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    usuarios = db.query(User).filter(User.orgao_id == ctx["orgao_id"]).order_by(User.nome).all()
    unidades = db.query(Unidade).filter(Unidade.orgao_id == ctx["orgao_id"]).order_by(Unidade.nome).all()
    return templates.TemplateResponse(
        "paiol/forms/deposito_form.html",
        _form_ctx(request, action="add", usuarios=usuarios, unidades=unidades),
    )


@router.post("/depositos/add")
def deposito_add(
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    unidade_id: Optional[int] = Form(None),
    responsavel_id: Optional[int] = Form(None),
    endereco: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    db.add(
        PaiolDeposito(
            codigo=codigo.strip().upper(),
            nome=nome.strip(),
            municipio_id=ctx["municipio_id"],
            orgao_id=ctx["orgao_id"],
            unidade_id=unidade_id or None,
            responsavel_id=responsavel_id or None,
            endereco=endereco.strip() or None,
        )
    )
    db.commit()
    log_paiol(db, user, request, f"Cadastrou depósito {nome.strip()}")
    return RedirectResponse("/paiol/cadastro/depositos", status_code=HTTP_302_FOUND)


@router.get("/depositos/edit/{item_id}")
def deposito_edit_form(item_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolDeposito).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/depositos", status_code=HTTP_302_FOUND)
    usuarios = db.query(User).filter(User.orgao_id == item.orgao_id).order_by(User.nome).all()
    unidades = db.query(Unidade).filter(Unidade.orgao_id == item.orgao_id).order_by(Unidade.nome).all()
    return templates.TemplateResponse(
        "paiol/forms/deposito_form.html",
        _form_ctx(request, action="edit", item=item, usuarios=usuarios, unidades=unidades),
    )


@router.post("/depositos/edit/{item_id}")
def deposito_edit(
    item_id: int,
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    unidade_id: Optional[int] = Form(None),
    responsavel_id: Optional[int] = Form(None),
    endereco: str = Form(""),
    ativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolDeposito).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/depositos", status_code=HTTP_302_FOUND)
    item.codigo = codigo.strip().upper()
    item.nome = nome.strip()
    item.unidade_id = unidade_id or None
    item.responsavel_id = responsavel_id or None
    item.endereco = endereco.strip() or None
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou depósito {nome.strip()} (ID {item_id})")
    return RedirectResponse("/paiol/cadastro/depositos", status_code=HTTP_302_FOUND)


# ── Localizações ───────────────────────────────────────────

@router.get("/localizacoes/add")
def localizacao_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    depositos = db.query(PaiolDeposito).filter(PaiolDeposito.orgao_id == ctx["orgao_id"], PaiolDeposito.ativo == True).all()
    return templates.TemplateResponse("paiol/forms/localizacao_form.html", _form_ctx(request, action="add", depositos=depositos))


@router.post("/localizacoes/add")
def localizacao_add(
    request: Request,
    deposito_id: int = Form(...),
    codigo: str = Form(...),
    descricao: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    db.add(PaiolLocalizacao(deposito_id=deposito_id, codigo=codigo.strip().upper(), descricao=descricao.strip() or None))
    db.commit()
    log_paiol(db, user, request, f"Cadastrou localização {codigo.strip().upper()}")
    return RedirectResponse("/paiol/cadastro/localizacoes", status_code=HTTP_302_FOUND)


@router.get("/localizacoes/edit/{item_id}")
def localizacao_edit_form(item_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolLocalizacao).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/localizacoes", status_code=HTTP_302_FOUND)
    depositos = db.query(PaiolDeposito).filter(PaiolDeposito.ativo == True).order_by(PaiolDeposito.nome).all()
    return templates.TemplateResponse("paiol/forms/localizacao_form.html", _form_ctx(request, action="edit", item=item, depositos=depositos))


@router.post("/localizacoes/edit/{item_id}")
def localizacao_edit(
    item_id: int,
    request: Request,
    deposito_id: int = Form(...),
    codigo: str = Form(...),
    descricao: str = Form(""),
    ativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolLocalizacao).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/localizacoes", status_code=HTTP_302_FOUND)
    item.deposito_id = deposito_id
    item.codigo = codigo.strip().upper()
    item.descricao = descricao.strip() or None
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou localização {codigo.strip().upper()} (ID {item_id})")
    return RedirectResponse("/paiol/cadastro/localizacoes", status_code=HTTP_302_FOUND)


# ── Materiais ──────────────────────────────────────────────

def _material_form_data(db: Session, ctx: dict, tipo_default: str | None = None, cancel_url: str | None = None):
    return {
        "classes": db.query(PaiolClasseMaterial).filter(PaiolClasseMaterial.ativo == True).order_by(PaiolClasseMaterial.nome).all(),
        "fabricantes": db.query(PaiolFabricante).filter(PaiolFabricante.ativo == True).order_by(PaiolFabricante.nome).all(),
        "tipos": TIPO_MATERIAL_LABELS,
        "tipo_default": tipo_default,
        "cancel_url": cancel_url or material_list_url(tipo_default),
        "municipio_id": ctx["municipio_id"],
        "orgao_id": ctx["orgao_id"],
    }


@router.get("/materiais/add")
def material_add_form(request: Request, tipo: str | None = None, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    return templates.TemplateResponse(
        "paiol/forms/material_form.html",
        _form_ctx(request, action="add", **_material_form_data(db, ctx, tipo)),
    )


@router.post("/materiais/add")
def material_add(
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    tipo: str = Form(...),
    descricao: str = Form(""),
    calibre: str = Form(""),
    classe_id: Optional[int] = Form(None),
    fabricante_id: Optional[int] = Form(None),
    controla_por_serie: Optional[str] = Form(None),
    controla_lote: Optional[str] = Form(None),
    quantidade_minima: int = Form(0),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    db.add(
        PaiolMaterial(
            codigo=codigo.strip().upper(),
            nome=nome.strip(),
            tipo=tipo,
            descricao=descricao.strip() or None,
            calibre=calibre.strip() or None,
            classe_id=classe_id or None,
            fabricante_id=fabricante_id or None,
            municipio_id=ctx["municipio_id"],
            orgao_id=ctx["orgao_id"],
            controla_por_serie=controla_por_serie == "on",
            controla_lote=controla_lote == "on",
            quantidade_minima=quantidade_minima or 0,
            created_by=ctx["user_id"],
        )
    )
    db.commit()
    log_paiol(db, user, request, f"Cadastrou material {nome.strip()} ({tipo})")
    return RedirectResponse(material_list_url(tipo), status_code=HTTP_302_FOUND)


@router.get("/materiais/edit/{item_id}")
def material_edit_form(item_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolMaterial).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/materiais", status_code=HTTP_302_FOUND)
    ctx = user_context(db, user)
    return templates.TemplateResponse(
        "paiol/forms/material_form.html",
        _form_ctx(request, action="edit", item=item, **_material_form_data(db, ctx, item.tipo, material_list_url(item.tipo))),
    )


@router.post("/materiais/edit/{item_id}")
def material_edit(
    item_id: int,
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    tipo: str = Form(...),
    descricao: str = Form(""),
    calibre: str = Form(""),
    classe_id: Optional[int] = Form(None),
    fabricante_id: Optional[int] = Form(None),
    controla_por_serie: Optional[str] = Form(None),
    controla_lote: Optional[str] = Form(None),
    quantidade_minima: int = Form(0),
    ativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolMaterial).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/materiais", status_code=HTTP_302_FOUND)
    item.codigo = codigo.strip().upper()
    item.nome = nome.strip()
    item.tipo = tipo
    item.descricao = descricao.strip() or None
    item.calibre = calibre.strip() or None
    item.classe_id = classe_id or None
    item.fabricante_id = fabricante_id or None
    item.controla_por_serie = controla_por_serie == "on"
    item.controla_lote = controla_lote == "on"
    item.quantidade_minima = quantidade_minima or 0
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou material {nome.strip()} (ID {item_id})")
    return RedirectResponse(material_list_url(item.tipo), status_code=HTTP_302_FOUND)


# ── Usuários autorizados ───────────────────────────────────

@router.get("/usuarios-autorizados/add")
def usuario_add_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    ctx = user_context(db, user)
    usuarios = db.query(User).filter(User.orgao_id == ctx["orgao_id"]).order_by(User.nome).all()
    depositos = db.query(PaiolDeposito).filter(PaiolDeposito.orgao_id == ctx["orgao_id"]).all()
    classes = db.query(PaiolClasseMaterial).filter(PaiolClasseMaterial.ativo == True).all()
    return templates.TemplateResponse(
        "paiol/forms/usuario_autorizado_form.html",
        _form_ctx(request, action="add", usuarios=usuarios, depositos=depositos, classes=classes),
    )


@router.post("/usuarios-autorizados/add")
def usuario_add(
    request: Request,
    user_id: int = Form(...),
    deposito_id: Optional[int] = Form(None),
    classe_id: Optional[int] = Form(None),
    operacoes: str = Form(""),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    db.add(
        PaiolUsuarioAutorizado(
            user_id=user_id,
            deposito_id=deposito_id or None,
            classe_id=classe_id or None,
            operacoes=operacoes.strip() or None,
        )
    )
    db.commit()
    log_paiol(db, user, request, f"Cadastrou usuário autorizado (user_id {user_id})")
    return RedirectResponse("/paiol/cadastro/usuarios-autorizados", status_code=HTTP_302_FOUND)


@router.get("/usuarios-autorizados/edit/{item_id}")
def usuario_edit_form(item_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolUsuarioAutorizado).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/usuarios-autorizados", status_code=HTTP_302_FOUND)
    usuarios = db.query(User).order_by(User.nome).all()
    depositos = db.query(PaiolDeposito).order_by(PaiolDeposito.nome).all()
    classes = db.query(PaiolClasseMaterial).filter(PaiolClasseMaterial.ativo == True).all()
    return templates.TemplateResponse(
        "paiol/forms/usuario_autorizado_form.html",
        _form_ctx(request, action="edit", item=item, usuarios=usuarios, depositos=depositos, classes=classes),
    )


@router.post("/usuarios-autorizados/edit/{item_id}")
def usuario_edit(
    item_id: int,
    request: Request,
    user_id: int = Form(...),
    deposito_id: Optional[int] = Form(None),
    classe_id: Optional[int] = Form(None),
    operacoes: str = Form(""),
    ativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _redirect_login(user):
        return r
    item = db.query(PaiolUsuarioAutorizado).get(item_id)
    if not item:
        return RedirectResponse("/paiol/cadastro/usuarios-autorizados", status_code=HTTP_302_FOUND)
    item.user_id = user_id
    item.deposito_id = deposito_id or None
    item.classe_id = classe_id or None
    item.operacoes = operacoes.strip() or None
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou usuário autorizado (ID {item_id})")
    return RedirectResponse("/paiol/cadastro/usuarios-autorizados", status_code=HTTP_302_FOUND)
