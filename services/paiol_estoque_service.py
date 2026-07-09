"""Operações de estoque do módulo Paiol (saldos + movimentações)."""

from datetime import datetime

from sqlalchemy.orm import Session

from models import PaiolDeposito, PaiolMaterial, PaiolMovimentacao, PaiolSaldo
from paiol_constants import TipoMovimentacaoPaiol


class PaiolEstoqueError(ValueError):
    """Erro de validação ou regra de negócio do estoque paiol."""


def _get_material(db: Session, material_id: int) -> PaiolMaterial:
    material = db.query(PaiolMaterial).filter(PaiolMaterial.id == material_id).first()
    if not material:
        raise PaiolEstoqueError("Material não encontrado.")
    if not material.ativo:
        raise PaiolEstoqueError("Material inativo.")
    if material.controla_por_serie:
        raise PaiolEstoqueError(
            "Este material é controlado por série. Movimentação por quantidade não está disponível nesta versão."
        )
    return material


def _get_deposito(db: Session, deposito_id: int, orgao_id: int) -> PaiolDeposito:
    deposito = (
        db.query(PaiolDeposito)
        .filter(PaiolDeposito.id == deposito_id, PaiolDeposito.orgao_id == orgao_id, PaiolDeposito.ativo == True)
        .first()
    )
    if not deposito:
        raise PaiolEstoqueError("Depósito não encontrado ou inativo.")
    return deposito


def _find_saldo(
    db: Session,
    material_id: int,
    deposito_id: int,
    localizacao_id: int | None = None,
) -> PaiolSaldo | None:
    q = db.query(PaiolSaldo).filter(
        PaiolSaldo.material_id == material_id,
        PaiolSaldo.deposito_id == deposito_id,
    )
    if localizacao_id:
        q = q.filter(PaiolSaldo.localizacao_id == localizacao_id)
    else:
        q = q.filter(PaiolSaldo.localizacao_id.is_(None))
    return q.first()


def get_saldo_atual(
    db: Session,
    material_id: int,
    deposito_id: int,
    localizacao_id: int | None = None,
) -> dict:
    saldo = _find_saldo(db, material_id, deposito_id, localizacao_id)
    material = db.query(PaiolMaterial).get(material_id)
    minimo = 0
    if saldo:
        minimo = saldo.quantidade_minima or (material.quantidade_minima if material else 0)
        return {"quantidade": saldo.quantidade, "quantidade_minima": minimo, "existe": True}
    minimo = material.quantidade_minima if material else 0
    return {"quantidade": 0, "quantidade_minima": minimo, "existe": False}


def _get_or_create_saldo(
    db: Session,
    ctx: dict,
    material: PaiolMaterial,
    deposito: PaiolDeposito,
    localizacao_id: int | None = None,
) -> PaiolSaldo:
    saldo = _find_saldo(db, material.id, deposito.id, localizacao_id)
    if saldo:
        return saldo
    saldo = PaiolSaldo(
        municipio_id=ctx["municipio_id"],
        orgao_id=ctx["orgao_id"],
        material_id=material.id,
        deposito_id=deposito.id,
        localizacao_id=localizacao_id,
        quantidade=0,
        quantidade_minima=material.quantidade_minima or 0,
    )
    db.add(saldo)
    db.flush()
    return saldo


def _registrar_mov(
    db: Session,
    ctx: dict,
    tipo: str,
    material_id: int,
    quantidade: int,
    deposito_origem_id: int | None,
    deposito_destino_id: int | None,
    observacao: str | None,
    requisicao_id: int | None = None,
) -> PaiolMovimentacao:
    mov = PaiolMovimentacao(
        material_id=material_id,
        deposito_origem_id=deposito_origem_id,
        deposito_destino_id=deposito_destino_id,
        quantidade=quantidade,
        tipo=tipo,
        status="executado",
        data=datetime.utcnow(),
        observacao=observacao,
        user_id=ctx["user_id"],
        requisicao_id=requisicao_id,
    )
    db.add(mov)
    db.flush()
    return mov


def registrar_entrada(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    localizacao_id: int | None = None,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    if quantidade <= 0:
        raise PaiolEstoqueError("Quantidade deve ser maior que zero.")
    material = _get_material(db, material_id)
    deposito = _get_deposito(db, deposito_id, ctx["orgao_id"])
    saldo = _get_or_create_saldo(db, ctx, material, deposito, localizacao_id)
    saldo.quantidade += quantidade
    mov = _registrar_mov(
        db,
        ctx,
        TipoMovimentacaoPaiol.ENTRADA.value,
        material.id,
        quantidade,
        None,
        deposito.id,
        observacao,
    )
    from services.paiol_custodia_service import registrar_evento_movimentacao

    registrar_evento_movimentacao(db, ctx, mov)
    db.commit()
    return mov


def registrar_saida(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade: int,
    localizacao_id: int | None = None,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    if quantidade <= 0:
        raise PaiolEstoqueError("Quantidade deve ser maior que zero.")
    material = _get_material(db, material_id)
    deposito = _get_deposito(db, deposito_id, ctx["orgao_id"])
    saldo = _find_saldo(db, material.id, deposito.id, localizacao_id)
    if not saldo or saldo.quantidade < quantidade:
        disponivel = saldo.quantidade if saldo else 0
        raise PaiolEstoqueError(f"Saldo insuficiente. Disponível: {disponivel}.")
    saldo.quantidade -= quantidade
    mov = _registrar_mov(
        db,
        ctx,
        TipoMovimentacaoPaiol.SAIDA.value,
        material.id,
        quantidade,
        deposito.id,
        None,
        observacao,
    )
    from services.paiol_custodia_service import registrar_evento_movimentacao

    registrar_evento_movimentacao(db, ctx, mov)
    db.commit()
    return mov


def registrar_transferencia(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_origem_id: int,
    deposito_destino_id: int,
    quantidade: int,
    localizacao_origem_id: int | None = None,
    localizacao_destino_id: int | None = None,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    if quantidade <= 0:
        raise PaiolEstoqueError("Quantidade deve ser maior que zero.")
    if deposito_origem_id == deposito_destino_id and localizacao_origem_id == localizacao_destino_id:
        raise PaiolEstoqueError("Origem e destino devem ser diferentes.")
    material = _get_material(db, material_id)
    dep_origem = _get_deposito(db, deposito_origem_id, ctx["orgao_id"])
    dep_destino = _get_deposito(db, deposito_destino_id, ctx["orgao_id"])
    saldo_origem = _find_saldo(db, material.id, dep_origem.id, localizacao_origem_id)
    if not saldo_origem or saldo_origem.quantidade < quantidade:
        disponivel = saldo_origem.quantidade if saldo_origem else 0
        raise PaiolEstoqueError(f"Saldo insuficiente na origem. Disponível: {disponivel}.")
    saldo_origem.quantidade -= quantidade
    saldo_destino = _get_or_create_saldo(db, ctx, material, dep_destino, localizacao_destino_id)
    saldo_destino.quantidade += quantidade
    mov = _registrar_mov(
        db,
        ctx,
        TipoMovimentacaoPaiol.TRANSFERENCIA.value,
        material.id,
        quantidade,
        dep_origem.id,
        dep_destino.id,
        observacao,
    )
    db.commit()
    return mov


def _ajustar_quantidade(
    db: Session,
    ctx: dict,
    tipo: str,
    material_id: int,
    deposito_id: int,
    quantidade_nova: int,
    localizacao_id: int | None = None,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    if quantidade_nova < 0:
        raise PaiolEstoqueError("Quantidade não pode ser negativa.")
    if not (observacao or "").strip():
        raise PaiolEstoqueError("Informe o motivo da operação no campo observação.")
    material = _get_material(db, material_id)
    deposito = _get_deposito(db, deposito_id, ctx["orgao_id"])
    saldo = _get_or_create_saldo(db, ctx, material, deposito, localizacao_id)
    anterior = saldo.quantidade
    delta = quantidade_nova - anterior
    if delta == 0:
        raise PaiolEstoqueError("A quantidade informada é igual ao saldo atual.")
    saldo.quantidade = quantidade_nova
    mov = _registrar_mov(
        db,
        ctx,
        tipo,
        material.id,
        abs(delta),
        deposito.id if delta < 0 else None,
        deposito.id if delta > 0 else None,
        f"{observacao.strip()} (anterior: {anterior} → novo: {quantidade_nova})",
    )
    db.commit()
    return mov


def registrar_ajuste(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade_nova: int,
    localizacao_id: int | None = None,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    return _ajustar_quantidade(
        db,
        ctx,
        TipoMovimentacaoPaiol.AJUSTE.value,
        material_id,
        deposito_id,
        quantidade_nova,
        localizacao_id,
        observacao,
    )


def registrar_inventario(
    db: Session,
    ctx: dict,
    material_id: int,
    deposito_id: int,
    quantidade_contada: int,
    localizacao_id: int | None = None,
    observacao: str | None = None,
) -> PaiolMovimentacao:
    obs = observacao or "Inventário físico"
    return _ajustar_quantidade(
        db,
        ctx,
        TipoMovimentacaoPaiol.INVENTARIO.value,
        material_id,
        deposito_id,
        quantidade_contada,
        localizacao_id,
        obs,
    )
