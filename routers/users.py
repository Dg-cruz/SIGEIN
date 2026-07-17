from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from starlette.status import HTTP_302_FOUND
from database import get_db
from dependencies import get_current_user, registrar_log
from models import (
    User,
    Municipio,
    Orgao,
    Unidade,
    Perfil,
    PerfilEnum,
    StatusUsuarioEnum,
    Log,
    Movement,
    Processo,
    ProcessoAssinante,
    Tramite,
    Product,
    SegemItem,
)
from templating import templates
from typing import Optional
import re
import hashlib

router = APIRouter(prefix="/users", tags=["Users"])


def _perfil_valor(user: User) -> str:
    return user._perfil_valor()


def _perfis_disponiveis(db: Session, incluir_id: Optional[int] = None):
    """Perfis ativos (sistema + personalizados) para o select de usuário."""
    if incluir_id:
        q = db.query(Perfil).filter((Perfil.ativo == True) | (Perfil.id == incluir_id))
    else:
        q = db.query(Perfil).filter(Perfil.ativo == True)
    return q.order_by(Perfil.sistema.desc(), Perfil.nome).all()


def _parse_perfil_id(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _perfil_id_do_usuario(user: User, db: Session) -> Optional[int]:
    if user.perfil_personalizado_id:
        return user.perfil_personalizado_id
    codigo = _perfil_valor(user)
    p = db.query(Perfil).filter(Perfil.codigo == codigo).first()
    return p.id if p else None


def _resolver_perfil(db: Session, perfil_id: Optional[int]) -> Optional[Perfil]:
    if not perfil_id:
        return None
    return db.query(Perfil).filter(Perfil.id == perfil_id).first()


def _role_e_vinculo(perfil_row: Perfil):
    """Retorna (valor PerfilEnum, id do perfil na tabela perfis)."""
    codigos = {e.value for e in PerfilEnum}
    if perfil_row.codigo and perfil_row.codigo in codigos:
        return perfil_row.codigo, perfil_row.id
    return PerfilEnum.OPERADOR.value, perfil_row.id


def _is_master(user: User) -> bool:
    return _perfil_valor(user) == PerfilEnum.MASTER.value


def _is_admin_municipal(user: User) -> bool:
    return _perfil_valor(user) == PerfilEnum.ADMIN_MUNICIPAL.value


# ========================================
# HELPERS
# ========================================

def validar_cpf(cpf: str) -> bool:
    """Valida CPF brasileiro"""
    cpf = re.sub(r'\D', '', cpf)
    
    if len(cpf) != 11:
        return False
    
    if cpf == cpf[0] * 11:
        return False
    
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    if int(cpf[9]) != digito1:
        return False
    
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    if int(cpf[10]) != digito2:
        return False
    
    return True


def hash_senha(senha: str) -> str:
    """Cria hash SHA256 da senha (em produção use bcrypt)"""
    return hashlib.sha256(senha.encode()).hexdigest()


def limpar_cpf(cpf: str) -> str:
    """Remove formatação do CPF"""
    return re.sub(r'\D', '', cpf)


def _form_data_from_request(
    nome,
    cpf,
    email,
    municipio_id,
    orgao_id,
    unidade_id,
    status,
    db: Session,
    perfil_id=None,
):
    """Monta dict para reexibir o formulário com valores preenchidos."""
    estado_id = None
    if municipio_id and db:
        m = db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if m:
            estado_id = m.estado_id
    return {
        "nome": nome or "",
        "cpf": cpf or "",
        "email": email or "",
        "municipio_id": municipio_id or "",
        "orgao_id": orgao_id or "",
        "unidade_id": unidade_id or "",
        "estado_id": estado_id or "",
        "status": status or "",
        "perfil_id": perfil_id or "",
    }


# ========================================
# LISTAR USUÁRIOS
# ========================================

@router.get("/")
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()

    if not user_obj:
        return RedirectResponse("/login")

    if not user_obj.pode_gerenciar_usuarios():
        return HTMLResponse(
            "<h2>Acesso Negado</h2><p>Você não tem permissão para gerenciar usuários.</p>",
            status_code=403,
        )

    if _is_master(user_obj):
        users = db.query(User).order_by(User.nome).all()
    else:
        users = (
            db.query(User)
            .filter(User.municipio_id == user_obj.municipio_id)
            .order_by(User.nome)
            .all()
        )

    def _status_val(u: User) -> str:
        s = u.status
        return s.value if hasattr(s, "value") else str(s)

    total_users = len(users)
    active_count = sum(1 for u in users if _status_val(u) == StatusUsuarioEnum.ATIVO.value)
    pending_count = sum(1 for u in users if _status_val(u) == StatusUsuarioEnum.PENDENTE.value)
    inactive_count = total_users - active_count - pending_count

    return templates.TemplateResponse(
        "users_list.html",
        {
            "request": request,
            "hide_app_header": True,
            "users": users,
            "user": current_user,
            "user_perfil": _perfil_valor(user_obj),
            "total_users": total_users,
            "active_count": active_count,
            "pending_count": pending_count,
            "inactive_count": inactive_count,
        },
    )



# ========================================
# FORMULÁRIO DE CADASTRO
# ========================================

@router.get("/add")
def add_user_form(
    request: Request,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()

    if not user_obj.pode_gerenciar_usuarios():
        return HTMLResponse("Acesso Negado", status_code=403)

    return templates.TemplateResponse(
        "user_form.html",
        {
            "request": request,
            "user": None,
            "action": "add",
            "current_user": current_user,
            "perfis_disponiveis": _perfis_disponiveis(db),
            "selected_perfil_id": None,
        }
    )


# ========================================
# INSERÇÃO NO BANCO
# ========================================

@router.post("/add")
def add_user(
    request: Request,
    nome: str = Form(...),
    cpf: str = Form(...),
    email: str = Form(...),
    municipio_id: int = Form(...),
    orgao_id: int = Form(...),
    unidade_id: int = Form(...),
    perfil_id: str = Form(...),
    status: str = Form(...),
    senha: str = Form(...),
    confirmar_senha: str = Form(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()

    if not user_obj.pode_gerenciar_usuarios():
        raise HTTPException(status_code=403, detail="Sem permissão")

    cpf_limpo = limpar_cpf(cpf)
    pid = _parse_perfil_id(perfil_id)
    perfil_row = _resolver_perfil(db, pid)
    perfis_ctx = _perfis_disponiveis(db, pid)

    def _error_response(errors):
        form_data = _form_data_from_request(
            nome, cpf, email, municipio_id, orgao_id, unidade_id, status, db, pid
        )
        return templates.TemplateResponse("user_form.html", {
            "request": request, "user": None, "action": "add", "current_user": current_user,
            "form_data": form_data, "errors": errors,
            "perfis_disponiveis": perfis_ctx,
            "selected_perfil_id": pid,
        })

    if not validar_cpf(cpf_limpo):
        return _error_response(["CPF inválido. Verifique o número digitado."])

    if senha != confirmar_senha:
        return _error_response(["As senhas não coincidem."])

    if len(senha) < 6:
        return _error_response(["A senha deve ter no mínimo 6 caracteres."])

    if db.query(User).filter(User.cpf == cpf_limpo).first():
        return _error_response(["Este CPF já está cadastrado."])

    if db.query(User).filter(User.email == email).first():
        return _error_response(["Este e-mail já está cadastrado."])

    if _is_admin_municipal(user_obj) and municipio_id != user_obj.municipio_id:
        raise HTTPException(status_code=403, detail="Você só pode criar usuários do seu município")

    if not perfil_row or not perfil_row.ativo:
        return _error_response(["Selecione um perfil válido."])

    role_valor, vinculo_id = _role_e_vinculo(perfil_row)

    if role_valor == PerfilEnum.MASTER.value and not _is_master(user_obj):
        raise HTTPException(status_code=403, detail="Apenas MASTER pode criar outros usuários MASTER")

    novo_usuario = User(
        nome=nome,
        cpf=cpf_limpo,
        email=email,
        password=hash_senha(senha),
        municipio_id=municipio_id,
        orgao_id=orgao_id,
        unidade_id=unidade_id,
        perfil=role_valor,
        status=status,
        perfil_personalizado_id=vinculo_id,
        created_by=user_obj.id
    )

    db.add(novo_usuario)
    db.commit()

    registrar_log(
        db,
        usuario=current_user,
        acao=f"Cadastrou usuário {nome} (CPF: {cpf_limpo}, Perfil: {perfil_row.nome})",
        ip=request.client.host
    )

    return RedirectResponse("/users", status_code=HTTP_302_FOUND)


# ========================================
# FORMULÁRIO DE EDIÇÃO
# ========================================

@router.get("/edit/{user_id}")
def edit_user_form(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")
    
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    # ✅ Verifica permissão
    if not user_obj.pode_gerenciar_usuarios():
        return HTMLResponse("Acesso Negado", status_code=403)
    
    # ✅ Busca usuário a editar
    user_to_edit = db.query(User).filter(User.id == user_id).first()
    if not user_to_edit:
        return HTMLResponse("Usuário não encontrado", status_code=404)
    
    # ✅ ADMIN_MUNICIPAL só pode editar usuários do seu município
    # ❌ ANTES: if user_obj.perfil.value == "admin_municipal":
    # ✅ DEPOIS:
    if _is_admin_municipal(user_obj):
        if user_to_edit.municipio_id != user_obj.municipio_id:
            return HTMLResponse("Você só pode editar usuários do seu município", status_code=403)
    
    if _is_master(user_to_edit) and not _is_master(user_obj):
        return HTMLResponse("Apenas MASTER pode editar outros MASTER", status_code=403)
    
    return templates.TemplateResponse(
        "user_form.html",
        {
            "request": request,
            "user": user_to_edit,
            "action": "edit",
            "current_user": current_user,
            "selected_perfil_id": _perfil_id_do_usuario(user_to_edit, db),
            "perfis_disponiveis": _perfis_disponiveis(
                db, user_to_edit.perfil_personalizado_id
            ),
        }
    )


# ========================================
# ATUALIZAÇÃO DO USUÁRIO
# ========================================

@router.post("/edit/{user_id}")
def edit_user(
    request: Request,
    user_id: int,
    nome: str = Form(...),
    cpf: str = Form(...),
    email: str = Form(...),
    municipio_id: int = Form(...),
    orgao_id: int = Form(...),
    unidade_id: int = Form(...),
    perfil_id: str = Form(...),
    status: str = Form(...),
    senha: str = Form(""),
    confirmar_senha: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")
    
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    # ✅ Verifica permissão
    if not user_obj.pode_gerenciar_usuarios():
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    # ✅ Busca usuário
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # ✅ Validações
    cpf_limpo = limpar_cpf(cpf)
    pid = _parse_perfil_id(perfil_id)
    perfil_row = _resolver_perfil(db, pid)
    perfis_ctx = _perfis_disponiveis(db, pid or user.perfil_personalizado_id)
    form_data = _form_data_from_request(
        nome, cpf, email, municipio_id, orgao_id, unidade_id, status, db, pid
    )

    def _error_response(errors):
        return templates.TemplateResponse("user_form.html", {
            "request": request, "user": user, "action": "edit", "current_user": current_user,
            "form_data": form_data, "errors": errors,
            "perfis_disponiveis": perfis_ctx,
            "selected_perfil_id": pid,
        })

    if not validar_cpf(cpf_limpo):
        return _error_response(["CPF inválido. Verifique o número digitado."])

    # ✅ Verifica se CPF já existe (exceto o próprio usuário)
    cpf_existe = db.query(User).filter(
        User.cpf == cpf_limpo,
        User.id != user_id
    ).first()
    if cpf_existe:
        return _error_response(["Este CPF já está cadastrado para outro usuário."])

    # ✅ Verifica se email já existe (exceto o próprio usuário)
    email_existe = db.query(User).filter(
        User.email == email,
        User.id != user_id
    ).first()
    if email_existe:
        return _error_response(["Este e-mail já está cadastrado para outro usuário."])

    # ✅ Valida senha (se fornecida)
    if senha:
        if senha != confirmar_senha:
            return _error_response(["As senhas não coincidem."])
        if len(senha) < 6:
            return _error_response(["A senha deve ter no mínimo 6 caracteres."])

    if not perfil_row:
        return _error_response(["Selecione um perfil válido."])

    role_valor, vinculo_id = _role_e_vinculo(perfil_row)

    if role_valor == PerfilEnum.MASTER.value and not _is_master(user_obj):
        raise HTTPException(status_code=403, detail="Apenas MASTER pode atribuir perfil MASTER")
    
    # ✅ ATUALIZA CAMPOS
    user.nome = nome
    user.cpf = cpf_limpo
    user.email = email
    user.municipio_id = municipio_id
    user.orgao_id = orgao_id
    user.unidade_id = unidade_id
    user.perfil = role_valor
    user.status = status
    user.perfil_personalizado_id = vinculo_id
    
    # ✅ Atualiza senha apenas se fornecida
    if senha:
        user.password = hash_senha(senha)
    
    db.commit()
    
    # ✅ LOG
    registrar_log(
        db,
        usuario=current_user,
        acao=f"Editou usuário {nome} (ID: {user_id})",
        ip=request.client.host
    )
    
    return RedirectResponse("/users", status_code=HTTP_302_FOUND)


# ========================================
# EXCLUIR USUÁRIO
# ========================================

def _liberar_vinculos_usuario(db: Session, user_id: int) -> None:
    """Remove ou desvincula registros que impedem a exclusão do usuário."""
    db.query(Log).filter(Log.user_id == user_id).delete(synchronize_session=False)

    db.query(Movement).filter(Movement.user_id == user_id).update(
        {Movement.user_id: None}, synchronize_session=False
    )

    db.query(ProcessoAssinante).filter(ProcessoAssinante.user_id == user_id).delete(
        synchronize_session=False
    )

    db.query(Processo).filter(Processo.atribuido_to_id == user_id).update(
        {Processo.atribuido_to_id: None}, synchronize_session=False
    )
    db.query(Processo).filter(Processo.arquivado_por_id == user_id).update(
        {Processo.arquivado_por_id: None}, synchronize_session=False
    )
    db.query(Processo).filter(Processo.created_by == user_id).update(
        {Processo.created_by: None}, synchronize_session=False
    )

    db.query(Tramite).filter(Tramite.created_by == user_id).update(
        {Tramite.created_by: None}, synchronize_session=False
    )
    db.query(Product).filter(Product.created_by == user_id).update(
        {Product.created_by: None}, synchronize_session=False
    )
    db.query(SegemItem).filter(SegemItem.created_by == user_id).update(
        {SegemItem.created_by: None}, synchronize_session=False
    )
    db.query(User).filter(User.created_by == user_id).update(
        {User.created_by: None}, synchronize_session=False
    )

    db.execute(
        text(
            "UPDATE processo_movimentacoes SET created_by = NULL WHERE created_by = :uid"
        ),
        {"uid": user_id},
    )


@router.post("/delete/{user_id}")
def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    if not current_user:
        return JSONResponse({"success": False, "message": "Não autenticado"})
    
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    # ✅ Verifica permissão
    if not user_obj.pode_gerenciar_usuarios():
        return JSONResponse({"success": False, "message": "Sem permissão"})
    
    # ✅ Busca usuário a excluir
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    if not user_to_delete:
        return JSONResponse({"success": False, "message": "Usuário não encontrado"})
    
    # ✅ Impede exclusão do próprio usuário
    if user_to_delete.id == user_obj.id:
        return JSONResponse({"success": False, "message": "Você não pode excluir a si mesmo"})
    
    # ✅ Apenas MASTER pode excluir outro MASTER
    # ❌ ANTES: if user_to_delete.perfil.value == "master" and user_obj.perfil.value != "master":
    # ✅ DEPOIS:
    if _is_master(user_to_delete) and not _is_master(user_obj):
        return JSONResponse({"success": False, "message": "Apenas MASTER pode excluir outro MASTER"})
    
    if _is_admin_municipal(user_obj):
        if user_to_delete.municipio_id != user_obj.municipio_id:
            return JSONResponse({"success": False, "message": "Você só pode excluir usuários do seu município"})

    nome_excluido = user_to_delete.nome

    try:
        _liberar_vinculos_usuario(db, user_id)
        db.delete(user_to_delete)
        db.commit()
    except IntegrityError:
        db.rollback()
        return JSONResponse(
            {
                "success": False,
                "message": (
                    "Não foi possível excluir: o usuário ainda possui vínculos "
                    "no sistema (movimentações, processos ou outros registros)."
                ),
            },
        )

    registrar_log(
        db,
        usuario=current_user,
        acao=f"Excluiu usuário {nome_excluido} (ID: {user_id})",
        ip=request.client.host,
        user_id=user_obj.id,
        tipo="seguranca",
    )

    return JSONResponse({"success": True, "message": "Usuário excluído com sucesso"})