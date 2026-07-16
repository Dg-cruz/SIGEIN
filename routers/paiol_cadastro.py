from datetime import date
from typing import Optional
import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND

from database import get_db
from dependencies import get_current_user
from services.paiol_audit import log_paiol
from services.paiol_helpers import opcoes_campos_tipo_material, user_context
from services.restcountries_service import listar_paises
from templating import format_cnpj, limpar_cnpj, templates
from models import (
    PaiolClasseMaterial,
    PaiolDeposito,
    PaiolFabricante,
    PaiolFornecedor,
    PaiolLocalizacao,
    PaiolMaterial,
    PaiolMunicao,
    PaiolTipoMaterial,
    PaiolUsuarioAutorizado,
    Unidade,
    User,
)
from paiol_constants import (
    CategoriaTipoMaterial,
    CATEGORIA_TIPO_MATERIAL_CAMPOS,
    CATEGORIA_TIPO_MATERIAL_LABELS,
    CATEGORIA_TIPO_PREFIX,
    MUNICAO_QUANTIDADE_TIPOS,
    TIPO_MATERIAL_LABELS,
    TipoMaterialPaiol,
    material_list_url,
)

_CATEGORIAS_VALIDAS = {c.value for c in CategoriaTipoMaterial}
_municao_schema_ready = False


def _ensure_municao_columns() -> None:
    """Garante colunas lote/validade em bancos já existentes."""
    global _municao_schema_ready
    if _municao_schema_ready:
        return
    try:
        from sqlalchemy import inspect, text
        from database import engine

        insp = inspect(engine)
        if "paiol_municoes" not in insp.get_table_names():
            _municao_schema_ready = True
            return
        cols = {c["name"] for c in insp.get_columns("paiol_municoes")}
        alters = []
        if "lote" not in cols:
            alters.append("ADD COLUMN lote VARCHAR(80)")
        if "validade" not in cols:
            alters.append("ADD COLUMN validade DATE")
        if alters:
            with engine.begin() as conn:
                for stmt in alters:
                    conn.execute(text(f"ALTER TABLE paiol_municoes {stmt}"))
        _municao_schema_ready = True
    except Exception:
        pass



def _extrair_campos_tipo(categoria: str, data: dict) -> tuple[str | None, dict | None, str | None]:
    """Retorna (especie, detalhes, mensagem_erro)."""
    campos = CATEGORIA_TIPO_MATERIAL_CAMPOS.get(categoria, [])
    if not campos:
        return None, None, "Categoria sem campos configurados."

    especie = ""
    detalhes: dict = {}
    for campo in campos:
        nome = campo["name"]
        valor = (data.get(nome) or "").strip() if isinstance(data.get(nome), str) else data.get(nome)
        if campo.get("required") and not valor:
            return None, None, f"Informe o campo {campo['label']}."
        if nome == "especie":
            especie = str(valor or "").strip()
        else:
            detalhes[nome] = str(valor or "").strip()

    if not especie:
        return None, None, "Informe a espécie."

    return especie, detalhes or None, None


def _tipo_duplicado(
    db: Session,
    categoria: str,
    especie: str,
    detalhes: dict | None,
    exclude_id: int | None = None,
) -> bool:
    registros = db.query(PaiolTipoMaterial).filter(PaiolTipoMaterial.categoria == categoria).all()
    for row in registros:
        if exclude_id and row.id == exclude_id:
            continue
        if categoria == CategoriaTipoMaterial.ARMAMENTO.value and detalhes:
            serie = (detalhes.get("numero_serie") or "").strip()
            if serie and (row.detalhes or {}).get("numero_serie") == serie:
                return True
            continue
        if row.especie == especie:
            return True
    return False


router = APIRouter(prefix="/paiol/cadastro", tags=["Paiol — Cadastro"])


def _redirect_login(user: str):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


def _api_auth(user: str):
    if not user:
        return JSONResponse({"ok": False, "detail": "Não autenticado."}, status_code=401)
    return None


def _form_ctx(request: Request, **extra):
    return {"request": request, "hide_app_header": True, **extra}


def _normalizar_cnpj(value: str) -> str | None:
    digits = limpar_cnpj(value)
    if not digits:
        return None
    if len(digits) != 14:
        return digits
    return format_cnpj(digits)


def _gerar_codigo_municao(db: Session, nome: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "-", nome.strip().upper()).strip("-")[:24] or "MUNICAO"
    base = f"MUN-{slug}"
    codigo = base
    n = 1
    while db.query(PaiolMunicao).filter(PaiolMunicao.codigo == codigo).first():
        codigo = f"{base}-{n}"
        n += 1
    return codigo


def _parse_municao_payload(data: dict) -> tuple[dict | None, str | None]:
    nome = (data.get("nome_comercial") or "").strip()
    calibre = (data.get("calibre") or "").strip()
    fabricante = (data.get("fabricante_marca") or "").strip()
    lote = (data.get("lote") or "").strip()
    validade_raw = (data.get("validade") or "").strip()
    q_tipo = (data.get("quantidade_tipo") or "").strip().lower()
    q_valor_raw = data.get("quantidade_valor")
    tipos_validos = {t[0] for t in MUNICAO_QUANTIDADE_TIPOS}

    if not nome:
        return None, "Informe a descrição / nome comercial."
    if not calibre:
        return None, "Informe o calibre."
    if not fabricante:
        return None, "Selecione o fabricante / marca."
    if not lote:
        return None, "Informe o lote."
    if not validade_raw:
        return None, "Informe a validade."
    try:
        validade = date.fromisoformat(validade_raw[:10])
    except ValueError:
        return None, "Informe a validade no formato AAAA-MM-DD."
    if q_tipo not in tipos_validos:
        return None, "Selecione o tipo de quantidade (Unidade ou Caixa)."
    try:
        q_valor = int(q_valor_raw)
    except (TypeError, ValueError):
        return None, "Informe a quantidade numérica."
    if q_valor < 1:
        return None, "A quantidade deve ser maior que zero."

    return {
        "nome_comercial": nome,
        "calibre": calibre,
        "fabricante_marca": fabricante,
        "lote": lote[:80],
        "validade": validade,
        "quantidade_tipo": q_tipo,
        "quantidade_valor": q_valor,
    }, None


def _aplicar_fabricante_municao(db: Session, dados: dict) -> str | None:
    fab = (
        db.query(PaiolFabricante)
        .filter(PaiolFabricante.nome == dados["fabricante_marca"], PaiolFabricante.ativo == True)
        .first()
    )
    if not fab:
        return "Selecione um fabricante cadastrado em Fabricantes."
    dados["fabricante_id"] = fab.id
    return None


def _gerar_codigo_tipo(db: Session, categoria: str, especie: str, detalhes: dict | None = None) -> str:
    prefix = CATEGORIA_TIPO_PREFIX.get(categoria, "TIP")
    if categoria == CategoriaTipoMaterial.ARMAMENTO.value and detalhes:
        serie = re.sub(r"[^A-Z0-9]+", "-", (detalhes.get("numero_serie") or "").strip().upper()).strip("-")
        if serie:
            base = f"{prefix}-{serie[:20]}"
        else:
            slug = re.sub(r"[^A-Z0-9]+", "-", especie.strip().upper()).strip("-")[:24] or "SEM-NOME"
            base = f"{prefix}-{slug}"
    else:
        slug = re.sub(r"[^A-Z0-9]+", "-", especie.strip().upper()).strip("-")[:24] or "SEM-NOME"
        base = f"{prefix}-{slug}"
    codigo = base
    n = 1
    while db.query(PaiolTipoMaterial).filter(PaiolTipoMaterial.codigo == codigo).first():
        codigo = f"{base}-{n}"
        n += 1
    return codigo


def _validar_opcoes_armamento(db: Session, detalhes: dict | None) -> str | None:
    if not detalhes:
        return None
    nome = (detalhes.get("marca_fabricante") or "").strip()
    calibre = (detalhes.get("calibre") or "").strip()
    if nome:
        fab = db.query(PaiolFabricante).filter(
            PaiolFabricante.nome == nome,
            PaiolFabricante.ativo == True,
        ).first()
        if not fab:
            return "Selecione um fabricante cadastrado em Fabricantes."
        detalhes["fabricante_id"] = fab.id
    if calibre:
        mun = db.query(PaiolMunicao).filter(
            PaiolMunicao.calibre == calibre,
            PaiolMunicao.ativo == True,
        ).first()
        if not mun:
            return "Selecione um calibre cadastrado em Munições."
        detalhes["municao_id"] = mun.id
    return None


# ── Tipos de material ──────────────────────────────────────

@router.get("/tipos-material/opcoes")
def tipo_material_opcoes(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if r := _api_auth(user):
        return r
    return JSONResponse({"ok": True, "opcoes": opcoes_campos_tipo_material(db)})


# ── Tipos de material (API) ────────────────────────────────

@router.get("/tipos-material/api/{item_id}")
def tipo_material_api_get(
    item_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    item = db.query(PaiolTipoMaterial).get(item_id)
    if not item:
        return JSONResponse({"ok": False, "detail": "Registro não encontrado."}, status_code=404)
    return JSONResponse(
        {
            "ok": True,
            "item": {
                "id": item.id,
                "codigo": item.codigo,
                "categoria": item.categoria,
                "especie": item.especie,
                "descricao": item.descricao or "",
                "detalhes": item.detalhes or {},
                "ativo": item.ativo,
            },
        }
    )


@router.post("/tipos-material/api")
async def tipo_material_api_create(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    data = await request.json()
    categoria = (data.get("categoria") or "").strip()
    descricao = (data.get("descricao") or "").strip() or None
    if categoria not in _CATEGORIAS_VALIDAS:
        return JSONResponse({"ok": False, "detail": "Categoria inválida."}, status_code=400)

    # Armamentos e munições vão para as tabelas das telas específicas
    if categoria == CategoriaTipoMaterial.ARMAMENTO.value:
        ctx = user_context(db, user)
        dados, erro = _parse_armamento_payload(data)
        if erro:
            return JSONResponse({"ok": False, "detail": erro}, status_code=400)
        item, erro = _criar_armamento(db, ctx, dados)
        if erro:
            return JSONResponse({"ok": False, "detail": erro}, status_code=400)
        db.commit()
        db.refresh(item)
        log_paiol(db, user, request, f"Cadastrou armamento {item.nome} ({item.codigo})")
        return JSONResponse({"ok": True, "id": item.id, "redirect": "/paiol/cadastro/materiais-belicos"})

    if categoria == CategoriaTipoMaterial.MUNICOES_EXPLOSIVOS.value:
        _ensure_municao_columns()
        dados, erro = _parse_municao_payload(data)
        if erro:
            return JSONResponse({"ok": False, "detail": erro}, status_code=400)
        erro_fab = _aplicar_fabricante_municao(db, dados)
        if erro_fab:
            return JSONResponse({"ok": False, "detail": erro_fab}, status_code=400)
        item = PaiolMunicao(
            codigo=_gerar_codigo_municao(db, dados["nome_comercial"]),
            nome_comercial=dados["nome_comercial"],
            calibre=dados["calibre"],
            fabricante_marca=dados.get("fabricante_marca"),
            fabricante_id=dados.get("fabricante_id"),
            quantidade_tipo=dados.get("quantidade_tipo"),
            quantidade_valor=dados.get("quantidade_valor"),
            lote=dados.get("lote"),
            validade=dados.get("validade"),
            descricao=dados.get("descricao"),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        log_paiol(db, user, request, f"Cadastrou munição {item.nome_comercial} ({item.codigo})")
        return JSONResponse({"ok": True, "id": item.id, "redirect": "/paiol/cadastro/municoes"})

    especie, detalhes, erro = _extrair_campos_tipo(categoria, data)
    if erro:
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    if _tipo_duplicado(db, categoria, especie, detalhes):
        return JSONResponse({"ok": False, "detail": "Já existe um tipo com esta categoria e espécie."}, status_code=400)
    item = PaiolTipoMaterial(
        codigo=_gerar_codigo_tipo(db, categoria, especie, detalhes),
        categoria=categoria,
        especie=especie,
        descricao=descricao,
        detalhes=detalhes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    log_paiol(db, user, request, f"Cadastrou tipo de material {item.especie} ({item.codigo})")
    return JSONResponse({"ok": True, "id": item.id})


@router.post("/tipos-material/api/{item_id}")
async def tipo_material_api_update(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    item = db.query(PaiolTipoMaterial).get(item_id)
    if not item:
        return JSONResponse({"ok": False, "detail": "Registro não encontrado."}, status_code=404)
    data = await request.json()
    categoria = (data.get("categoria") or "").strip()
    descricao = (data.get("descricao") or "").strip() or None
    ativo = data.get("ativo", True)
    if categoria not in _CATEGORIAS_VALIDAS:
        return JSONResponse({"ok": False, "detail": "Categoria inválida."}, status_code=400)
    especie, detalhes, erro = _extrair_campos_tipo(categoria, data)
    if erro:
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    if categoria == CategoriaTipoMaterial.ARMAMENTO.value:
        erro_opcoes = _validar_opcoes_armamento(db, detalhes)
        if erro_opcoes:
            return JSONResponse({"ok": False, "detail": erro_opcoes}, status_code=400)
    if _tipo_duplicado(db, categoria, especie, detalhes, exclude_id=item_id):
        msg = "Já existe um armamento com este número de série." if categoria == CategoriaTipoMaterial.ARMAMENTO.value else "Já existe um tipo com esta categoria e espécie."
        return JSONResponse({"ok": False, "detail": msg}, status_code=400)
    if item.categoria != categoria or item.especie != especie or item.detalhes != detalhes:
        item.codigo = _gerar_codigo_tipo(db, categoria, especie, detalhes)
    item.categoria = categoria
    item.especie = especie
    item.descricao = descricao
    item.detalhes = detalhes
    item.ativo = bool(ativo)
    db.commit()
    log_paiol(db, user, request, f"Editou tipo de material {item.especie} (ID {item_id})")
    return JSONResponse({"ok": True})


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

@router.get("/fabricantes/paises")
def fabricante_paises(user: str = Depends(get_current_user)):
    if r := _redirect_login(user):
        return r
    return JSONResponse({"ok": True, "paises": listar_paises()})


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
    db.add(PaiolFabricante(nome=nome.strip(), pais=pais.strip() or None, cnpj=_normalizar_cnpj(cnpj)))
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
    item.cnpj = _normalizar_cnpj(cnpj)
    item.ativo = ativo == "on"
    db.commit()
    log_paiol(db, user, request, f"Editou fabricante {nome.strip()} (ID {item_id})")
    return RedirectResponse("/paiol/cadastro/fabricantes", status_code=HTTP_302_FOUND)


# ── Munições ───────────────────────────────────────────────

@router.get("/municoes/api/{item_id}")
def municao_api_get(
    item_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    _ensure_municao_columns()
    item = db.query(PaiolMunicao).get(item_id)
    if not item:
        return JSONResponse({"ok": False, "detail": "Registro não encontrado."}, status_code=404)
    return JSONResponse(
        {
            "ok": True,
            "item": {
                "id": item.id,
                "codigo": item.codigo,
                "nome_comercial": item.nome_comercial,
                "calibre": item.calibre,
                "fabricante_marca": item.fabricante_marca or "",
                "lote": item.lote or "",
                "validade": item.validade.isoformat() if item.validade else "",
                "quantidade_tipo": item.quantidade_tipo or "",
                "quantidade_valor": item.quantidade_valor or "",
                "ativo": item.ativo,
            },
        }
    )


@router.post("/municoes/api")
async def municao_api_create(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    _ensure_municao_columns()
    data = await request.json()
    dados, erro = _parse_municao_payload(data)
    if erro:
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    if erro := _aplicar_fabricante_municao(db, dados):
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    item = PaiolMunicao(
        codigo=_gerar_codigo_municao(db, dados["nome_comercial"]),
        nome_comercial=dados["nome_comercial"],
        calibre=dados["calibre"],
        fabricante_marca=dados["fabricante_marca"],
        fabricante_id=dados.get("fabricante_id"),
        lote=dados["lote"],
        validade=dados["validade"],
        quantidade_tipo=dados["quantidade_tipo"],
        quantidade_valor=dados["quantidade_valor"],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    log_paiol(db, user, request, f"Cadastrou munição {item.nome_comercial} ({item.codigo})")
    return JSONResponse({"ok": True, "id": item.id})


@router.post("/municoes/api/{item_id}")
async def municao_api_update(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    _ensure_municao_columns()
    item = db.query(PaiolMunicao).get(item_id)
    if not item:
        return JSONResponse({"ok": False, "detail": "Registro não encontrado."}, status_code=404)
    data = await request.json()
    dados, erro = _parse_municao_payload(data)
    if erro:
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    if erro := _aplicar_fabricante_municao(db, dados):
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    if item.nome_comercial != dados["nome_comercial"]:
        item.codigo = _gerar_codigo_municao(db, dados["nome_comercial"])
    item.nome_comercial = dados["nome_comercial"]
    item.calibre = dados["calibre"]
    item.fabricante_marca = dados["fabricante_marca"]
    item.fabricante_id = dados.get("fabricante_id")
    item.lote = dados["lote"]
    item.validade = dados["validade"]
    item.quantidade_tipo = dados["quantidade_tipo"]
    item.quantidade_valor = dados["quantidade_valor"]
    item.ativo = bool(data.get("ativo", True))
    db.commit()
    log_paiol(db, user, request, f"Editou munição {item.nome_comercial} (ID {item_id})")
    return JSONResponse({"ok": True})


# ── Armamentos (bridge a partir de Tipos de materiais) ─────

_ARMAMENTO_ESPECIES = ("Pistola", "Revólver", "Espingarda", "Carabina", "Rifle")


def _serie_from_descricao(descricao: str | None) -> str:
    if not descricao:
        return ""
    if descricao.startswith("Série: "):
        return descricao.replace("Série: ", "", 1).strip()
    return ""


def _parse_nome_armamento(nome: str | None) -> tuple[str, str]:
    nome = (nome or "").strip()
    if not nome:
        return "", ""
    for especie in _ARMAMENTO_ESPECIES:
        if nome == especie:
            return especie, ""
        prefix = especie + " "
        if nome.startswith(prefix):
            return especie, nome[len(prefix):].strip()
    parts = nome.split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def armamento_view(item: PaiolMaterial) -> dict:
    especie, modelo = _parse_nome_armamento(item.nome)
    return {
        "id": item.id,
        "codigo": item.codigo,
        "especie": especie,
        "modelo": modelo,
        "marca_fabricante": item.fabricante.nome if item.fabricante else "",
        "numero_serie": _serie_from_descricao(item.descricao),
        "calibre": item.calibre or "",
        "ativo": item.ativo,
    }


def _criar_armamento(db: Session, ctx: dict, dados: dict) -> tuple[PaiolMaterial | None, str | None]:
    fab = (
        db.query(PaiolFabricante)
        .filter(PaiolFabricante.nome == dados["marca_fabricante"], PaiolFabricante.ativo == True)
        .first()
    )
    if not fab:
        return None, "Selecione um fabricante cadastrado em Fabricantes."
    mun = (
        db.query(PaiolMunicao)
        .filter(PaiolMunicao.calibre == dados["calibre"], PaiolMunicao.ativo == True)
        .first()
    )
    if not mun:
        return None, "Selecione um calibre cadastrado em Munições e Químicos."
    if _serie_armamento_duplicada(db, dados["numero_serie"]):
        return None, "Já existe um armamento com este número de série."

    item = PaiolMaterial(
        codigo=_gerar_codigo_armamento(db, dados["numero_serie"]),
        nome=f"{dados['especie']} {dados['modelo']}".strip(),
        tipo=TipoMaterialPaiol.ARMA.value,
        descricao=f"Série: {dados['numero_serie']}",
        calibre=dados["calibre"],
        fabricante_id=fab.id,
        municipio_id=ctx["municipio_id"],
        orgao_id=ctx["orgao_id"],
        controla_por_serie=True,
        controla_lote=False,
        quantidade_minima=0,
        created_by=ctx["user_id"],
    )
    db.add(item)
    db.flush()
    return item, None


def migrar_tipos_armamento_para_materiais(db: Session, ctx: dict) -> int:
    """Converte registros antigos de tipos (categoria armamento) em PaiolMaterial."""
    tipos = (
        db.query(PaiolTipoMaterial)
        .filter(PaiolTipoMaterial.categoria == CategoriaTipoMaterial.ARMAMENTO.value)
        .all()
    )
    migrados = 0
    for tipo in tipos:
        detalhes = tipo.detalhes or {}
        dados = {
            "especie": (tipo.especie or "").strip(),
            "marca_fabricante": (detalhes.get("marca_fabricante") or "").strip(),
            "modelo": (detalhes.get("modelo") or "").strip(),
            "numero_serie": (detalhes.get("numero_serie") or "").strip(),
            "calibre": (detalhes.get("calibre") or "").strip(),
        }
        if not all(dados.values()):
            continue
        if _serie_armamento_duplicada(db, dados["numero_serie"]):
            db.delete(tipo)
            migrados += 1
            continue
        # fabricante por id legado, se nome não bater
        if not dados["marca_fabricante"] and detalhes.get("fabricante_id"):
            fab = db.query(PaiolFabricante).filter(PaiolFabricante.id == detalhes["fabricante_id"]).first()
            if fab:
                dados["marca_fabricante"] = fab.nome
        item, erro = _criar_armamento(db, ctx, dados)
        if erro or not item:
            continue
        if tipo.ativo is False:
            item.ativo = False
        db.delete(tipo)
        migrados += 1
    if migrados:
        db.commit()
    return migrados


def _parse_armamento_payload(data: dict) -> tuple[dict | None, str | None]:
    especie = (data.get("especie") or "").strip()
    marca = (data.get("marca_fabricante") or "").strip()
    modelo = (data.get("modelo") or "").strip()
    serie = (data.get("numero_serie") or "").strip()
    calibre = (data.get("calibre") or "").strip()
    if not especie:
        return None, "Informe a espécie."
    if not marca:
        return None, "Selecione a marca / fabricante."
    if not modelo:
        return None, "Informe o modelo."
    if not serie:
        return None, "Informe o número de série."
    if not calibre:
        return None, "Selecione o calibre."
    return {
        "especie": especie,
        "marca_fabricante": marca,
        "modelo": modelo,
        "numero_serie": serie,
        "calibre": calibre,
    }, None


def _gerar_codigo_armamento(db: Session, numero_serie: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "-", numero_serie.strip().upper()).strip("-")[:20] or "SERIE"
    base = f"ARM-{slug}"
    codigo = base
    n = 1
    while db.query(PaiolMaterial).filter(PaiolMaterial.codigo == codigo).first():
        codigo = f"{base}-{n}"
        n += 1
    return codigo


def _serie_armamento_duplicada(db: Session, numero_serie: str, exclude_id: int | None = None) -> bool:
    serie = (numero_serie or "").strip()
    if not serie:
        return False
    query = db.query(PaiolMaterial).filter(PaiolMaterial.tipo == TipoMaterialPaiol.ARMA.value)
    if exclude_id is not None:
        query = query.filter(PaiolMaterial.id != exclude_id)
    for row in query.all():
        desc = row.descricao or ""
        if f"Série: {serie}" == desc or desc.endswith(f"Série: {serie}"):
            return True
        if row.codigo and serie.upper().replace("-", "") in (row.codigo or "").upper().replace("-", ""):
            # também considera código gerado a partir da série
            slug = re.sub(r"[^A-Z0-9]+", "", serie.upper())
            cod_slug = re.sub(r"[^A-Z0-9]+", "", (row.codigo or "").upper())
            if slug and slug in cod_slug:
                return True
    return False


@router.get("/armamentos/api/{item_id}")
def armamento_api_get(
    item_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    item = db.query(PaiolMaterial).filter(
        PaiolMaterial.id == item_id,
        PaiolMaterial.tipo == TipoMaterialPaiol.ARMA.value,
    ).first()
    if not item:
        return JSONResponse({"ok": False, "detail": "Registro não encontrado."}, status_code=404)
    return JSONResponse({"ok": True, "item": armamento_view(item)})


@router.post("/armamentos/api")
async def armamento_api_create(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    ctx = user_context(db, user)
    data = await request.json()
    dados, erro = _parse_armamento_payload(data)
    if erro:
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    item, erro = _criar_armamento(db, ctx, dados)
    if erro:
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    db.commit()
    db.refresh(item)
    log_paiol(db, user, request, f"Cadastrou armamento {item.nome} ({item.codigo})")
    return JSONResponse({"ok": True, "id": item.id})


@router.post("/armamentos/api/{item_id}")
async def armamento_api_update(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if r := _api_auth(user):
        return r
    item = db.query(PaiolMaterial).filter(
        PaiolMaterial.id == item_id,
        PaiolMaterial.tipo == TipoMaterialPaiol.ARMA.value,
    ).first()
    if not item:
        return JSONResponse({"ok": False, "detail": "Registro não encontrado."}, status_code=404)
    data = await request.json()
    dados, erro = _parse_armamento_payload(data)
    if erro:
        return JSONResponse({"ok": False, "detail": erro}, status_code=400)
    fab = (
        db.query(PaiolFabricante)
        .filter(PaiolFabricante.nome == dados["marca_fabricante"], PaiolFabricante.ativo == True)
        .first()
    )
    if not fab:
        return JSONResponse({"ok": False, "detail": "Selecione um fabricante cadastrado em Fabricantes."}, status_code=400)
    mun = (
        db.query(PaiolMunicao)
        .filter(PaiolMunicao.calibre == dados["calibre"], PaiolMunicao.ativo == True)
        .first()
    )
    if not mun:
        return JSONResponse({"ok": False, "detail": "Selecione um calibre cadastrado em Munições e Químicos."}, status_code=400)
    if _serie_armamento_duplicada(db, dados["numero_serie"], exclude_id=item_id):
        return JSONResponse({"ok": False, "detail": "Já existe um armamento com este número de série."}, status_code=400)

    serie_antiga = _serie_from_descricao(item.descricao)
    if serie_antiga != dados["numero_serie"]:
        item.codigo = _gerar_codigo_armamento(db, dados["numero_serie"])
    item.nome = f"{dados['especie']} {dados['modelo']}".strip()
    item.descricao = f"Série: {dados['numero_serie']}"
    item.calibre = dados["calibre"]
    item.fabricante_id = fab.id
    item.ativo = bool(data.get("ativo", True))
    db.commit()
    log_paiol(db, user, request, f"Editou armamento {item.nome} (ID {item_id})")
    return JSONResponse({"ok": True})


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
