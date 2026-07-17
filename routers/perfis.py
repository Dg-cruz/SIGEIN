from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from database import get_db
from dependencies import get_current_user, registrar_log
from models import User, Perfil, PerfilPermissao, PerfilEnum
from permissions_constants import MODULOS, ACOES, MODULO_KEYS
from templating import templates

router = APIRouter(prefix="/admin", tags=["Administração — Perfis e Módulos"])


def _perfil_valor(user: User) -> str:
    return user._perfil_valor()


def _require_admin(user_email: str | None, db: Session):
    if not user_email:
        return None, RedirectResponse("/login")
    user_obj = db.query(User).filter(User.email == user_email).first()
    if not user_obj:
        return None, RedirectResponse("/login")
    if _perfil_valor(user_obj) not in (
        PerfilEnum.MASTER.value,
        PerfilEnum.ADMIN_MUNICIPAL.value,
    ):
        return None, HTMLResponse(
            "<h2>Acesso Negado</h2><p>Você não tem permissão para gerenciar perfis e módulos.</p>",
            status_code=403,
        )
    return user_obj, None


# ========================================
# PERFIS — LISTA
# ========================================

@router.get("/perfis")
def list_perfis(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    user_obj, deny = _require_admin(user, db)
    if deny:
        return deny

    try:
        from services.perfis_service import _seed_perfis_sistema

        _seed_perfis_sistema()
    except Exception:
        pass

    perfis = db.query(Perfil).order_by(Perfil.sistema.desc(), Perfil.nome).all()
    return templates.TemplateResponse(
        "admin/perfis_list.html",
        {
            "request": request,
            "user": user,
            "hide_app_header": True,
            "perfis": perfis,
        },
    )


# ========================================
# PERFIS — ADD
# ========================================

@router.get("/perfis/add")
def add_perfil_form(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    _, deny = _require_admin(user, db)
    if deny:
        return deny

    return templates.TemplateResponse(
        "admin/perfil_form.html",
        {
            "request": request,
            "user": user,
            "hide_app_header": True,
            "action": "add",
            "perfil": None,
            "errors": [],
        },
    )


@router.post("/perfis/add")
def add_perfil(
    request: Request,
    nome: str = Form(...),
    descricao: str = Form(""),
    ativo: str = Form("false"),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    _, deny = _require_admin(user, db)
    if deny:
        return deny

    nome_limpo = (nome or "").strip()
    if not nome_limpo:
        return templates.TemplateResponse(
            "admin/perfil_form.html",
            {
                "request": request,
                "user": user,
                "hide_app_header": True,
                "action": "add",
                "perfil": None,
                "form_data": {"nome": nome, "descricao": descricao, "ativo": True},
                "errors": ["Informe o nome do perfil."],
            },
        )

    if db.query(Perfil).filter(Perfil.nome.ilike(nome_limpo)).first():
        return templates.TemplateResponse(
            "admin/perfil_form.html",
            {
                "request": request,
                "user": user,
                "hide_app_header": True,
                "action": "add",
                "perfil": None,
                "form_data": {"nome": nome_limpo, "descricao": descricao, "ativo": True},
                "errors": ["Já existe um perfil com este nome."],
            },
        )

    perfil = Perfil(
        nome=nome_limpo,
        descricao=(descricao or "").strip() or None,
        ativo=ativo and ativo.lower() in ("true", "1", "on", "sim"),
    )
    db.add(perfil)
    db.commit()
    db.refresh(perfil)

    registrar_log(
        db,
        usuario=user,
        acao=f"Cadastrou perfil personalizado: {perfil.nome} (ID {perfil.id})",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/perfis", status_code=HTTP_302_FOUND)


# ========================================
# PERFIS — EDIT
# ========================================

@router.get("/perfis/edit/{perfil_id}")
def edit_perfil_form(
    perfil_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    _, deny = _require_admin(user, db)
    if deny:
        return deny

    perfil = db.query(Perfil).filter(Perfil.id == perfil_id).first()
    if not perfil:
        return RedirectResponse("/admin/perfis", status_code=HTTP_302_FOUND)

    return templates.TemplateResponse(
        "admin/perfil_form.html",
        {
            "request": request,
            "user": user,
            "hide_app_header": True,
            "action": "edit",
            "perfil": perfil,
            "errors": [],
        },
    )


@router.post("/perfis/edit/{perfil_id}")
def edit_perfil(
    perfil_id: int,
    request: Request,
    nome: str = Form(...),
    descricao: str = Form(""),
    ativo: str = Form("false"),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    _, deny = _require_admin(user, db)
    if deny:
        return deny

    perfil = db.query(Perfil).filter(Perfil.id == perfil_id).first()
    if not perfil:
        return RedirectResponse("/admin/perfis", status_code=HTTP_302_FOUND)

    nome_limpo = (nome or "").strip()
    if not nome_limpo:
        return templates.TemplateResponse(
            "admin/perfil_form.html",
            {
                "request": request,
                "user": user,
                "hide_app_header": True,
                "action": "edit",
                "perfil": perfil,
                "form_data": {"nome": nome, "descricao": descricao, "ativo": perfil.ativo},
                "errors": ["Informe o nome do perfil."],
            },
        )

    duplicado = (
        db.query(Perfil)
        .filter(Perfil.nome.ilike(nome_limpo), Perfil.id != perfil_id)
        .first()
    )
    if duplicado:
        return templates.TemplateResponse(
            "admin/perfil_form.html",
            {
                "request": request,
                "user": user,
                "hide_app_header": True,
                "action": "edit",
                "perfil": perfil,
                "form_data": {"nome": nome_limpo, "descricao": descricao, "ativo": True},
                "errors": ["Já existe um perfil com este nome."],
            },
        )

    perfil.nome = nome_limpo
    perfil.descricao = (descricao or "").strip() or None
    perfil.ativo = ativo and ativo.lower() in ("true", "1", "on", "sim")
    # Perfis de sistema mantêm codigo/sistema
    if not (perfil.sistema or perfil.codigo):
        pass
    db.commit()

    registrar_log(
        db,
        usuario=user,
        acao=f"Editou perfil personalizado ID {perfil_id} ({perfil.nome})",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/perfis", status_code=HTTP_302_FOUND)


# ========================================
# PERFIS — DELETE
# ========================================

@router.post("/perfis/delete/{perfil_id}")
def delete_perfil(
    perfil_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    _, deny = _require_admin(user, db)
    if deny:
        if isinstance(deny, RedirectResponse):
            return JSONResponse({"success": False, "message": "Não autenticado"})
        return JSONResponse({"success": False, "message": "Sem permissão"})

    perfil = db.query(Perfil).filter(Perfil.id == perfil_id).first()
    if not perfil:
        return JSONResponse({"success": False, "message": "Perfil não encontrado"})

    if perfil.sistema or (perfil.codigo and perfil.codigo in {e.value for e in PerfilEnum}):
        return JSONResponse({
            "success": False,
            "message": "Perfis do sistema não podem ser excluídos.",
        })

    vinculados = db.query(User).filter(User.perfil_personalizado_id == perfil_id).count()
    if vinculados > 0:
        return JSONResponse({
            "success": False,
            "message": f"Não é possível excluir. Existem {vinculados} usuário(s) vinculado(s) a este perfil.",
        })

    nome = perfil.nome
    db.delete(perfil)
    db.commit()

    registrar_log(
        db,
        usuario=user,
        acao=f"Excluiu perfil personalizado {nome} (ID {perfil_id})",
        ip=request.client.host if request.client else None,
    )
    return JSONResponse({"success": True, "message": "Perfil excluído com sucesso"})


# ========================================
# MÓDULOS — MATRIZ DE PERMISSÕES
# ========================================

def _permissoes_map(perfil: Perfil) -> dict:
    """modulo -> dict de ações."""
    result = {}
    for p in perfil.permissoes or []:
        result[p.modulo] = {
            "visualizar": bool(p.visualizar),
            "inserir": bool(p.inserir),
            "editar": bool(p.editar),
            "excluir": bool(p.excluir),
        }
    return result


@router.get("/modulos")
def modulos_index(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    _, deny = _require_admin(user, db)
    if deny:
        return deny

    primeiro = db.query(Perfil).order_by(Perfil.nome).first()
    if primeiro:
        return RedirectResponse(f"/admin/modulos/{primeiro.id}", status_code=HTTP_302_FOUND)

    return templates.TemplateResponse(
        "admin/modulos.html",
        {
            "request": request,
            "user": user,
            "hide_app_header": True,
            "perfis": [],
            "perfil_sel": None,
            "modulos": MODULOS,
            "acoes": ACOES,
            "permissoes": {},
            "error": None,
            "ok": None,
        },
    )


@router.get("/modulos/{perfil_id}")
def modulos_matriz(
    perfil_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    ok: Optional[str] = None,
):
    _, deny = _require_admin(user, db)
    if deny:
        return deny

    perfis = db.query(Perfil).order_by(Perfil.nome).all()
    perfil_sel = (
        db.query(Perfil)
        .options(joinedload(Perfil.permissoes))
        .filter(Perfil.id == perfil_id)
        .first()
    )
    if not perfil_sel:
        return RedirectResponse("/admin/modulos", status_code=HTTP_302_FOUND)

    return templates.TemplateResponse(
        "admin/modulos.html",
        {
            "request": request,
            "user": user,
            "hide_app_header": True,
            "perfis": perfis,
            "perfil_sel": perfil_sel,
            "modulos": MODULOS,
            "acoes": ACOES,
            "permissoes": _permissoes_map(perfil_sel),
            "error": None,
            "ok": ok,
        },
    )


@router.post("/modulos/{perfil_id}")
async def salvar_modulos(
    perfil_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    _, deny = _require_admin(user, db)
    if deny:
        return deny

    perfil = (
        db.query(Perfil)
        .options(joinedload(Perfil.permissoes))
        .filter(Perfil.id == perfil_id)
        .first()
    )
    if not perfil:
        return RedirectResponse("/admin/modulos", status_code=HTTP_302_FOUND)

    form = await request.form()
    existentes = {p.modulo: p for p in (perfil.permissoes or [])}

    for modulo_key in MODULO_KEYS:
        visualizar = form.get(f"perm_{modulo_key}_visualizar") is not None
        inserir = form.get(f"perm_{modulo_key}_inserir") is not None
        editar = form.get(f"perm_{modulo_key}_editar") is not None
        excluir = form.get(f"perm_{modulo_key}_excluir") is not None
        algum = visualizar or inserir or editar or excluir

        row = existentes.get(modulo_key)
        if algum:
            if row:
                row.visualizar = visualizar
                row.inserir = inserir
                row.editar = editar
                row.excluir = excluir
            else:
                db.add(
                    PerfilPermissao(
                        perfil_id=perfil.id,
                        modulo=modulo_key,
                        visualizar=visualizar,
                        inserir=inserir,
                        editar=editar,
                        excluir=excluir,
                    )
                )
        elif row:
            db.delete(row)

    db.commit()

    registrar_log(
        db,
        usuario=user,
        acao=f"Atualizou permissões de módulos do perfil {perfil.nome} (ID {perfil_id})",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(
        f"/admin/modulos/{perfil_id}?ok=1",
        status_code=HTTP_302_FOUND,
    )
