from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

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
    PaiolMovimentacao,
    PaiolMunicao,
    PaiolSaldo,
    PaiolTipoMaterial,
    PaiolUsuarioAutorizado,
    User,
)
from paiol_constants import (
    CATEGORIA_TIPO_MATERIAL_CAMPOS,
    CATEGORIA_TIPO_MATERIAL_DESCRICOES,
    CATEGORIA_TIPO_MATERIAL_LABELS,
    MUNICAO_CAMPOS,
    MUNICAO_QUANTIDADE_TIPOS,
    TIPO_MATERIAL_LABELS,
    TipoMaterialPaiol,
    TipoMovimentacaoPaiol,
    TIPO_MOVIMENTO_LABELS,
)
from services.paiol_helpers import get_user_row, opcoes_campos_tipo_material
from services.paiol_service import build_paiol_alerts, build_paiol_dashboard_metrics
from services.paiol_estoque_service import get_saldo_atual
from services.paiol_shortcuts import (
    add_shortcut,
    list_available_shortcuts,
    list_user_shortcuts,
    remove_shortcut,
)
from templating import templates

router = APIRouter(prefix="/paiol", tags=["Paiol"])
legacy_router = APIRouter(tags=["Paiol — compatibilidade"])


def _user_display(db: Session, user: str) -> str:
    user_row = db.query(User).filter(User.email == user).first()
    if user_row and user_row.nome:
        return user_row.nome.split()[0]
    return user


def _auth_or_redirect(user: str):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


# ── Dashboard ──────────────────────────────────────────────

@router.get("/dashboard")
def paiol_dashboard(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    user_row = get_user_row(db, user)
    atalhos = list_user_shortcuts(db, user_row.id)
    return templates.TemplateResponse(
        "paiol_dashboard.html",
        {
            "request": request,
            "hide_app_header": True,
            "user_display": _user_display(db, user),
            "atalhos": atalhos,
            **build_paiol_dashboard_metrics(db),
        },
    )


class AtalhoCreate(BaseModel):
    menu_key: str


@router.get("/api/atalhos")
def api_list_atalhos(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    user_row = get_user_row(db, user)
    return JSONResponse({"atalhos": list_user_shortcuts(db, user_row.id)})


@router.get("/api/atalhos/disponiveis")
def api_atalhos_disponiveis(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    user_row = get_user_row(db, user)
    return JSONResponse({"itens": list_available_shortcuts(db, user_row.id)})


@router.post("/api/atalhos")
def api_add_atalho(
    payload: AtalhoCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        user_row = get_user_row(db, user)
        atalho = add_shortcut(db, user_row.id, payload.menu_key)
        log_paiol(db, user, request, f"Atalho adicionado na dashboard ({payload.menu_key})")
        return JSONResponse({"ok": True, "atalho": atalho})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.delete("/api/atalhos/{atalho_id}")
def api_remove_atalho(
    atalho_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    user_row = get_user_row(db, user)
    if not remove_shortcut(db, user_row.id, atalho_id):
        return JSONResponse({"error": "não encontrado"}, status_code=404)
    log_paiol(db, user, request, f"Atalho removido da dashboard (ID {atalho_id})")
    return JSONResponse({"ok": True})


@router.get("/api/data")
def paiol_api_data(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(build_paiol_dashboard_metrics(db))


@router.get("/api/saldo-atual")
def paiol_api_saldo_atual(
    material_id: int,
    deposito_id: int,
    localizacao_id: int | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(get_saldo_atual(db, material_id, deposito_id, localizacao_id))


# ── Cadastro ───────────────────────────────────────────────

def _materiais_por_tipo(db: Session, tipo: str | None = None):
    q = db.query(PaiolMaterial).options(
        joinedload(PaiolMaterial.classe),
        joinedload(PaiolMaterial.fabricante),
    )
    if tipo:
        q = q.filter(PaiolMaterial.tipo == tipo)
    return q.order_by(PaiolMaterial.nome).all()


@router.get("/cadastro/materiais")
def cadastro_materiais(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "paiol/cadastro_materiais.html",
        {
            "request": request,
            "hide_app_header": True,
            "materiais": _materiais_por_tipo(db),
            "titulo": "Todos os materiais",
            "tipo_filtro": None,
        },
    )


@router.get("/cadastro/materiais-belicos")
def cadastro_armas(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "paiol/cadastro_materiais.html",
        {
            "request": request,
            "hide_app_header": True,
            "materiais": _materiais_por_tipo(db, TipoMaterialPaiol.ARMA.value),
            "titulo": "Materiais bélicos (armas)",
            "tipo_filtro": TipoMaterialPaiol.ARMA.value,
        },
    )


@router.get("/cadastro/municoes")
def cadastro_municoes(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    municoes = db.query(PaiolMunicao).order_by(PaiolMunicao.nome_comercial).all()
    return templates.TemplateResponse(
        "paiol/cadastro_municoes.html",
        {
            "request": request,
            "hide_app_header": True,
            "municoes": municoes,
            "municao_campos": MUNICAO_CAMPOS,
            "quantidade_tipos": MUNICAO_QUANTIDADE_TIPOS,
            "opcoes_campos": opcoes_campos_tipo_material(db),
        },
    )


@router.get("/cadastro/explosivos")
def cadastro_explosivos(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "paiol/cadastro_materiais.html",
        {
            "request": request,
            "hide_app_header": True,
            "materiais": _materiais_por_tipo(db, TipoMaterialPaiol.EXPLOSIVO.value),
            "titulo": "Explosivos",
            "tipo_filtro": TipoMaterialPaiol.EXPLOSIVO.value,
        },
    )


@router.get("/cadastro/acessorios")
def cadastro_acessorios(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "paiol/cadastro_materiais.html",
        {
            "request": request,
            "hide_app_header": True,
            "materiais": _materiais_por_tipo(db, TipoMaterialPaiol.ACESSORIO.value),
            "titulo": "Acessórios",
            "tipo_filtro": TipoMaterialPaiol.ACESSORIO.value,
        },
    )


@router.get("/cadastro/classes")
def cadastro_classes(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    classes = db.query(PaiolClasseMaterial).order_by(PaiolClasseMaterial.nome).all()
    return templates.TemplateResponse(
        "paiol/cadastro_classes.html",
        {"request": request, "hide_app_header": True, "classes": classes},
    )


@router.get("/cadastro/tipos-material")
def cadastro_tipos_material(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    tipos = db.query(PaiolTipoMaterial).order_by(PaiolTipoMaterial.categoria, PaiolTipoMaterial.especie).all()
    categoria_labels = {k.value: v for k, v in CATEGORIA_TIPO_MATERIAL_LABELS.items()}
    categoria_descricoes = {k.value: v for k, v in CATEGORIA_TIPO_MATERIAL_DESCRICOES.items()}
    return templates.TemplateResponse(
        "paiol/cadastro_tipos_material.html",
        {
            "request": request,
            "hide_app_header": True,
            "tipos": tipos,
            "categoria_labels": categoria_labels,
            "categoria_descricoes": categoria_descricoes,
            "categoria_campos": CATEGORIA_TIPO_MATERIAL_CAMPOS,
            "opcoes_campos": opcoes_campos_tipo_material(db),
            "quantidade_tipos": MUNICAO_QUANTIDADE_TIPOS,
        },
    )


@router.get("/cadastro/fabricantes")
def cadastro_fabricantes(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    fabricantes = db.query(PaiolFabricante).order_by(PaiolFabricante.nome).all()
    return templates.TemplateResponse(
        "paiol/cadastro_fabricantes.html",
        {"request": request, "hide_app_header": True, "fabricantes": fabricantes},
    )


@router.get("/cadastro/fornecedores")
def cadastro_fornecedores(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    fornecedores = db.query(PaiolFornecedor).order_by(PaiolFornecedor.nome).all()
    return templates.TemplateResponse(
        "paiol/cadastro_fornecedores.html",
        {"request": request, "hide_app_header": True, "fornecedores": fornecedores},
    )


@router.get("/cadastro/depositos")
def cadastro_depositos(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    depositos = (
        db.query(PaiolDeposito)
        .options(joinedload(PaiolDeposito.orgao), joinedload(PaiolDeposito.responsavel))
        .order_by(PaiolDeposito.nome)
        .all()
    )
    return templates.TemplateResponse(
        "paiol/cadastro_depositos.html",
        {"request": request, "hide_app_header": True, "depositos": depositos},
    )


@router.get("/cadastro/localizacoes")
def cadastro_localizacoes(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    localizacoes = (
        db.query(PaiolLocalizacao)
        .options(joinedload(PaiolLocalizacao.deposito))
        .order_by(PaiolLocalizacao.codigo)
        .all()
    )
    return templates.TemplateResponse(
        "paiol/cadastro_localizacoes.html",
        {"request": request, "hide_app_header": True, "localizacoes": localizacoes},
    )


@router.get("/cadastro/usuarios-autorizados")
def cadastro_usuarios(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    registros = (
        db.query(PaiolUsuarioAutorizado)
        .options(
            joinedload(PaiolUsuarioAutorizado.user),
            joinedload(PaiolUsuarioAutorizado.deposito),
            joinedload(PaiolUsuarioAutorizado.classe),
        )
        .all()
    )
    return templates.TemplateResponse(
        "paiol/cadastro_usuarios.html",
        {"request": request, "hide_app_header": True, "registros": registros},
    )


# ── Estoque (consulta + operações em paiol_estoque.py) ──────

@router.get("/estoque/consulta")
def estoque_consulta(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    saldos = (
        db.query(PaiolSaldo)
        .options(
            joinedload(PaiolSaldo.material),
            joinedload(PaiolSaldo.deposito),
            joinedload(PaiolSaldo.localizacao),
        )
        .all()
    )
    return templates.TemplateResponse(
        "paiol/estoque_consulta.html",
        {"request": request, "hide_app_header": True, "saldos": saldos},
    )


def _placeholder(request: Request, titulo: str, descricao: str, fase: str = "Fase 2"):
    return templates.TemplateResponse(
        "paiol/placeholder.html",
        {
            "request": request,
            "hide_app_header": True,
            "titulo": titulo,
            "descricao": descricao,
            "fase": fase,
        },
    )


# ── Movimentações (histórico geral) ──────────────────────────

@router.get("/movimentacoes")
def movimentacoes_lista(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    movimentacoes = (
        db.query(PaiolMovimentacao)
        .options(
            joinedload(PaiolMovimentacao.material),
            joinedload(PaiolMovimentacao.user),
            joinedload(PaiolMovimentacao.deposito_origem),
            joinedload(PaiolMovimentacao.deposito_destino),
        )
        .order_by(PaiolMovimentacao.data.desc())
        .all()
    )
    return templates.TemplateResponse(
        "paiol/movimentacoes_list.html",
        {
            "request": request,
            "hide_app_header": True,
            "movimentacoes": movimentacoes,
            "tipos_mov": {t.value: TIPO_MOVIMENTO_LABELS[t] for t in TipoMovimentacaoPaiol},
        },
    )


# ── Segurança (auditoria permanece aqui; demais rotas em paiol_seguranca) ──

@router.get("/seguranca/auditoria")
def seguranca_auditoria(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    redirect = _auth_or_redirect(user)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "paiol/seguranca_auditoria.html",
        {"request": request, "hide_app_header": True, "alerts": build_paiol_alerts(db)},
    )


# ── Redirecionamentos legado belico ────────────────────────

_LEGACY_MAP = {
    "produtos": "/paiol/cadastro/materiais",
    "estoque": "/paiol/estoque/consulta",
    "movimentacoes": "/paiol/movimentacoes",
    "auditoria": "/paiol/seguranca/auditoria",
    "alertas": "/paiol/seguranca/auditoria",
    "api/data": "/paiol/api/data",
}


@legacy_router.get("/divisao-material-belico")
@legacy_router.get("/belico")
@legacy_router.get("/belico/")
def legacy_belico_dashboard():
    return RedirectResponse("/paiol/dashboard", status_code=302)


@legacy_router.get("/belico/{path:path}")
def legacy_belico_path(path: str):
    return RedirectResponse(_LEGACY_MAP.get(path, "/paiol/dashboard"), status_code=302)
