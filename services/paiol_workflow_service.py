"""Workflow de requisições e operações do módulo Paiol."""

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models import PaiolDeposito, PaiolMaterial, PaiolMovimentacao, PaiolRequisicao, PaiolRequisicaoItem, Unidade
from paiol_constants import StatusRequisicaoPaiol, TipoMovimentacaoPaiol
from services.paiol_assinatura_service import registrar_assinatura
from services.paiol_custodia_service import registrar_evento_movimentacao
from services.paiol_estoque_service import (
    PaiolEstoqueError,
    _find_saldo,
    _get_deposito,
    _get_material,
    _get_or_create_saldo,
    _registrar_mov,
)


class PaiolWorkflowError(ValueError):
    pass


def _gerar_numero(db: Session, orgao_id: int) -> str:
    ano = datetime.utcnow().year
    prefix = f"REQ-{ano}-"
    ultima = (
        db.query(PaiolRequisicao)
        .filter(PaiolRequisicao.orgao_id == orgao_id, PaiolRequisicao.numero.like(f"{prefix}%"))
        .order_by(PaiolRequisicao.id.desc())
        .first()
    )
    seq = 1
    if ultima and ultima.numero.startswith(prefix):
        try:
            seq = int(ultima.numero.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:05d}"


def listar_requisicoes(db: Session, orgao_id: int) -> list[PaiolRequisicao]:
    return (
        db.query(PaiolRequisicao)
        .options(
            joinedload(PaiolRequisicao.solicitante),
            joinedload(PaiolRequisicao.unidade),
            joinedload(PaiolRequisicao.deposito),
            joinedload(PaiolRequisicao.itens).joinedload(PaiolRequisicaoItem.material),
        )
        .filter(PaiolRequisicao.orgao_id == orgao_id)
        .order_by(PaiolRequisicao.created_at.desc())
        .all()
    )


def get_requisicao(db: Session, req_id: int, orgao_id: int) -> PaiolRequisicao:
    req = (
        db.query(PaiolRequisicao)
        .options(
            joinedload(PaiolRequisicao.solicitante),
            joinedload(PaiolRequisicao.aprovador),
            joinedload(PaiolRequisicao.unidade),
            joinedload(PaiolRequisicao.deposito),
            joinedload(PaiolRequisicao.itens).joinedload(PaiolRequisicaoItem.material),
        )
        .filter(PaiolRequisicao.id == req_id, PaiolRequisicao.orgao_id == orgao_id)
        .first()
    )
    if not req:
        raise PaiolWorkflowError("Requisição não encontrada.")
    return req


def criar_requisicao(
    db: Session,
    ctx: dict,
    *,
    unidade_id: int | None,
    deposito_id: int | None,
    observacao: str | None,
    itens: list[tuple[int, int]],
) -> PaiolRequisicao:
    if not itens:
        raise PaiolWorkflowError("Informe ao menos um item na requisição.")
    if deposito_id:
        _get_deposito(db, deposito_id, ctx["orgao_id"])
    if unidade_id:
        un = db.query(Unidade).filter(Unidade.id == unidade_id, Unidade.orgao_id == ctx["orgao_id"]).first()
        if not un:
            raise PaiolWorkflowError("Unidade não encontrada.")
    req = PaiolRequisicao(
        numero=_gerar_numero(db, ctx["orgao_id"]),
        orgao_id=ctx["orgao_id"],
        municipio_id=ctx["municipio_id"],
        solicitante_id=ctx["user_id"],
        unidade_id=unidade_id,
        deposito_id=deposito_id,
        status=StatusRequisicaoPaiol.RASCUNHO.value,
        observacao=(observacao or "").strip() or None,
    )
    db.add(req)
    db.flush()
    for material_id, qtd in itens:
        if qtd <= 0:
            raise PaiolWorkflowError("Quantidade deve ser maior que zero.")
        _get_material(db, material_id)
        db.add(
            PaiolRequisicaoItem(
                requisicao_id=req.id,
                material_id=material_id,
                quantidade_solicitada=qtd,
            )
        )
    db.commit()
    db.refresh(req)
    return req


def atualizar_requisicao(
    db: Session,
    ctx: dict,
    req_id: int,
    *,
    unidade_id: int | None,
    deposito_id: int | None,
    observacao: str | None,
    itens: list[tuple[int, int]],
) -> PaiolRequisicao:
    req = get_requisicao(db, req_id, ctx["orgao_id"])
    if req.status not in (StatusRequisicaoPaiol.RASCUNHO.value, StatusRequisicaoPaiol.PENDENTE.value):
        raise PaiolWorkflowError("Requisição não pode ser editada neste status.")
    if not itens:
        raise PaiolWorkflowError("Informe ao menos um item.")
    if deposito_id:
        _get_deposito(db, deposito_id, ctx["orgao_id"])
    req.unidade_id = unidade_id
    req.deposito_id = deposito_id
    req.observacao = (observacao or "").strip() or None
    req.updated_at = datetime.utcnow()
    for item in list(req.itens):
        db.delete(item)
    db.flush()
    for material_id, qtd in itens:
        if qtd <= 0:
            raise PaiolWorkflowError("Quantidade deve ser maior que zero.")
        _get_material(db, material_id)
        db.add(PaiolRequisicaoItem(requisicao_id=req.id, material_id=material_id, quantidade_solicitada=qtd))
    db.commit()
    return get_requisicao(db, req_id, ctx["orgao_id"])


def enviar_requisicao(db: Session, ctx: dict, req_id: int) -> PaiolRequisicao:
    req = get_requisicao(db, req_id, ctx["orgao_id"])
    if req.status != StatusRequisicaoPaiol.RASCUNHO.value:
        raise PaiolWorkflowError("Apenas rascunhos podem ser enviados para aprovação.")
    if not req.itens:
        raise PaiolWorkflowError("A requisição precisa de itens.")
    req.status = StatusRequisicaoPaiol.PENDENTE.value
    req.updated_at = datetime.utcnow()
    db.commit()
    return req


def aprovar_requisicao(db: Session, ctx: dict, req_id: int, observacao: str | None = None) -> PaiolRequisicao:
    req = get_requisicao(db, req_id, ctx["orgao_id"])
    if req.status != StatusRequisicaoPaiol.PENDENTE.value:
        raise PaiolWorkflowError("Apenas requisições pendentes podem ser aprovadas.")
    req.status = StatusRequisicaoPaiol.APROVADA.value
    req.aprovador_id = ctx["user_id"]
    req.aprovado_em = datetime.utcnow()
    req.motivo_rejeicao = None
    req.updated_at = datetime.utcnow()
    registrar_assinatura(db, ctx, "requisicao", req.id, observacao or f"Aprovação {req.numero}")
    db.commit()
    return req


def rejeitar_requisicao(db: Session, ctx: dict, req_id: int, motivo: str) -> PaiolRequisicao:
    req = get_requisicao(db, req_id, ctx["orgao_id"])
    if req.status != StatusRequisicaoPaiol.PENDENTE.value:
        raise PaiolWorkflowError("Apenas requisições pendentes podem ser rejeitadas.")
    if not (motivo or "").strip():
        raise PaiolWorkflowError("Informe o motivo da rejeição.")
    req.status = StatusRequisicaoPaiol.REJEITADA.value
    req.motivo_rejeicao = motivo.strip()
    req.aprovador_id = ctx["user_id"]
    req.aprovado_em = datetime.utcnow()
    req.updated_at = datetime.utcnow()
    db.commit()
    return req


def cancelar_requisicao(db: Session, ctx: dict, req_id: int) -> PaiolRequisicao:
    req = get_requisicao(db, req_id, ctx["orgao_id"])
    if req.status in (StatusRequisicaoPaiol.ATENDIDA.value, StatusRequisicaoPaiol.CANCELADA.value):
        raise PaiolWorkflowError("Requisição não pode ser cancelada.")
    req.status = StatusRequisicaoPaiol.CANCELADA.value
    req.updated_at = datetime.utcnow()
    db.commit()
    return req


def _atualizar_status_atendimento(req: PaiolRequisicao) -> None:
    total_sol = sum(i.quantidade_solicitada for i in req.itens)
    total_at = sum(i.quantidade_atendida for i in req.itens)
    if total_at >= total_sol:
        req.status = StatusRequisicaoPaiol.ATENDIDA.value
    elif total_at > 0:
        req.status = StatusRequisicaoPaiol.PARCIAL.value
    req.updated_at = datetime.utcnow()


def _saida_workflow(
    db: Session,
    ctx: dict,
    tipo: str,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    observacao: str | None,
    requisicao_id: int | None = None,
) -> PaiolMovimentacao:
    if quantidade <= 0:
        raise PaiolEstoqueError("Quantidade deve ser maior que zero.")
    material = _get_material(db, material_id)
    deposito = _get_deposito(db, deposito_id, ctx["orgao_id"])
    saldo = _find_saldo(db, material.id, deposito.id, None)
    if not saldo or saldo.quantidade < quantidade:
        disponivel = saldo.quantidade if saldo else 0
        raise PaiolEstoqueError(f"Saldo insuficiente. Disponível: {disponivel}.")
    saldo.quantidade -= quantidade
    mov = _registrar_mov(
        db,
        ctx,
        tipo,
        material.id,
        quantidade,
        deposito.id,
        None,
        observacao,
        requisicao_id=requisicao_id,
    )
    registrar_evento_movimentacao(db, ctx, mov)
    return mov


def _entrada_workflow(
    db: Session,
    ctx: dict,
    tipo: str,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    observacao: str | None,
    requisicao_id: int | None = None,
) -> PaiolMovimentacao:
    if quantidade <= 0:
        raise PaiolEstoqueError("Quantidade deve ser maior que zero.")
    material = _get_material(db, material_id)
    deposito = _get_deposito(db, deposito_id, ctx["orgao_id"])
    saldo = _get_or_create_saldo(db, ctx, material, deposito, None)
    saldo.quantidade += quantidade
    mov = _registrar_mov(
        db,
        ctx,
        tipo,
        material.id,
        quantidade,
        None,
        deposito.id,
        observacao,
        requisicao_id=requisicao_id,
    )
    registrar_evento_movimentacao(db, ctx, mov)
    return mov


def atender_requisicao(
    db: Session,
    ctx: dict,
    req_id: int,
    deposito_id: int,
    atendimentos: list[tuple[int, int]],
    observacao: str | None = None,
) -> list[PaiolMovimentacao]:
    req = get_requisicao(db, req_id, ctx["orgao_id"])
    if req.status not in (
        StatusRequisicaoPaiol.APROVADA.value,
        StatusRequisicaoPaiol.PARCIAL.value,
    ):
        raise PaiolWorkflowError("Requisição deve estar aprovada para distribuição.")
    if not atendimentos:
        raise PaiolWorkflowError("Informe as quantidades a distribuir.")
    _get_deposito(db, deposito_id, ctx["orgao_id"])
    movs: list[PaiolMovimentacao] = []
    itens_map = {i.id: i for i in req.itens}
    obs_base = observacao or f"Distribuição {req.numero}"
    for item_id, qtd in atendimentos:
        if qtd <= 0:
            continue
        item = itens_map.get(item_id)
        if not item:
            raise PaiolWorkflowError("Item inválido na distribuição.")
        pendente = item.quantidade_solicitada - item.quantidade_atendida
        if qtd > pendente:
            raise PaiolWorkflowError(f"Quantidade excede o pendente do item ({pendente}).")
        mov = _saida_workflow(
            db,
            ctx,
            TipoMovimentacaoPaiol.DISTRIBUICAO.value,
            item.material_id,
            deposito_id,
            qtd,
            obs_base,
            requisicao_id=req.id,
        )
        item.quantidade_atendida += qtd
        movs.append(mov)
    if not movs:
        raise PaiolWorkflowError("Nenhuma quantidade informada.")
    _atualizar_status_atendimento(req)
    db.commit()
    return movs


def registrar_devolucao(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    observacao: str | None = None,
    requisicao_id: int | None = None,
) -> PaiolMovimentacao:
    if not (observacao or "").strip():
        raise PaiolWorkflowError("Informe o motivo da devolução.")
    mov = _entrada_workflow(
        db,
        ctx,
        TipoMovimentacaoPaiol.DEVOLUCAO.value,
        material_id,
        deposito_id,
        quantidade,
        observacao.strip(),
        requisicao_id=requisicao_id,
    )
    db.commit()
    return mov


def registrar_baixa(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    if not (observacao or "").strip():
        raise PaiolWorkflowError("Informe o motivo da baixa.")
    mov = _saida_workflow(
        db,
        ctx,
        TipoMovimentacaoPaiol.BAIXA.value,
        material_id,
        deposito_id,
        quantidade,
        observacao.strip(),
    )
    db.commit()
    return mov


def registrar_cautela(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    if not (observacao or "").strip():
        raise PaiolWorkflowError("Informe o motivo da cautela.")
    mov = _saida_workflow(
        db,
        ctx,
        TipoMovimentacaoPaiol.CAUTELA.value,
        material_id,
        deposito_id,
        quantidade,
        observacao.strip(),
    )
    db.commit()
    return mov


def registrar_destruicao(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    observacao: str | None,
    conferente_id: int,
) -> PaiolMovimentacao:
    if not (observacao or "").strip():
        raise PaiolWorkflowError("Informe o processo e motivo da destruição.")
    if conferente_id == ctx["user_id"]:
        raise PaiolWorkflowError("O conferente deve ser diferente do operador.")
    obs = f"{observacao.strip()} | Conferente user_id={conferente_id}"
    mov = _saida_workflow(
        db,
        ctx,
        TipoMovimentacaoPaiol.DESTRUICAO.value,
        material_id,
        deposito_id,
        quantidade,
        obs,
    )
    registrar_assinatura(db, ctx, "destruicao", mov.id, "Registro de destruição")
    db.commit()
    return mov


def listar_movimentacoes_tipo(db: Session, orgao_id: int, tipo: str) -> list[PaiolMovimentacao]:
    return (
        db.query(PaiolMovimentacao)
        .join(PaiolMaterial)
        .options(
            joinedload(PaiolMovimentacao.material),
            joinedload(PaiolMovimentacao.user),
            joinedload(PaiolMovimentacao.deposito_origem),
            joinedload(PaiolMovimentacao.deposito_destino),
            joinedload(PaiolMovimentacao.requisicao),
        )
        .filter(PaiolMaterial.orgao_id == orgao_id, PaiolMovimentacao.tipo == tipo)
        .order_by(PaiolMovimentacao.data.desc())
        .all()
    )


def requisicoes_aprovadas(db: Session, orgao_id: int) -> list[PaiolRequisicao]:
    return (
        db.query(PaiolRequisicao)
        .options(joinedload(PaiolRequisicao.itens).joinedload(PaiolRequisicaoItem.material))
        .filter(
            PaiolRequisicao.orgao_id == orgao_id,
            PaiolRequisicao.status.in_(
                [StatusRequisicaoPaiol.APROVADA.value, StatusRequisicaoPaiol.PARCIAL.value]
            ),
        )
        .order_by(PaiolRequisicao.created_at.desc())
        .all()
    )
