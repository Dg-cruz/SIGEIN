"""Cadeia de custódia do módulo Paiol."""

from sqlalchemy.orm import Session, joinedload

from models import PaiolCustodiaEvento, PaiolMaterial, PaiolMovimentacao
from paiol_constants import TipoMovimentacaoPaiol

_EVENTO_POR_TIPO = {
    TipoMovimentacaoPaiol.ENTRADA.value: "ENTRADA",
    TipoMovimentacaoPaiol.SAIDA.value: "SAIDA",
    TipoMovimentacaoPaiol.TRANSFERENCIA.value: "TRANSFERENCIA",
    TipoMovimentacaoPaiol.DISTRIBUICAO.value: "DISTRIBUICAO",
    TipoMovimentacaoPaiol.DEVOLUCAO.value: "DEVOLUCAO",
    TipoMovimentacaoPaiol.BAIXA.value: "BAIXA",
    TipoMovimentacaoPaiol.DESTRUICAO.value: "DESTRUICAO",
    TipoMovimentacaoPaiol.CAUTELA.value: "CAUTELA",
    TipoMovimentacaoPaiol.AJUSTE.value: "AJUSTE",
    TipoMovimentacaoPaiol.INVENTARIO.value: "INVENTARIO",
}


def registrar_evento(
    db: Session,
    ctx: dict,
    evento: str,
    *,
    material_id: int | None = None,
    item_id: int | None = None,
    deposito_id: int | None = None,
    documento_ref: str | None = None,
    detalhes: str | None = None,
) -> PaiolCustodiaEvento:
    ev = PaiolCustodiaEvento(
        evento=evento,
        material_id=material_id,
        item_id=item_id,
        deposito_id=deposito_id,
        documento_ref=documento_ref,
        user_id=ctx["user_id"],
        detalhes=detalhes,
    )
    db.add(ev)
    db.flush()
    return ev


def registrar_evento_movimentacao(db: Session, ctx: dict, mov: PaiolMovimentacao) -> PaiolCustodiaEvento | None:
    evento = _EVENTO_POR_TIPO.get(mov.tipo)
    if not evento:
        return None
    deposito = mov.deposito_origem_id or mov.deposito_destino_id
    doc = None
    if mov.requisicao_id:
        doc = f"REQ#{mov.requisicao_id}"
    detalhes = f"Mov. #{mov.id} — {mov.tipo} — qtd {mov.quantidade}"
    if mov.observacao:
        detalhes = f"{detalhes}. {mov.observacao}"
    return registrar_evento(
        db,
        ctx,
        evento,
        material_id=mov.material_id,
        item_id=mov.item_id,
        deposito_id=deposito,
        documento_ref=doc,
        detalhes=detalhes,
    )


def listar_eventos(
    db: Session,
    orgao_id: int,
    *,
    material_id: int | None = None,
    limit: int = 500,
) -> list[PaiolCustodiaEvento]:
    q = (
        db.query(PaiolCustodiaEvento)
        .join(PaiolMaterial, PaiolCustodiaEvento.material_id == PaiolMaterial.id, isouter=True)
        .options(
            joinedload(PaiolCustodiaEvento.user),
            joinedload(PaiolCustodiaEvento.material),
        )
        .filter(
            (PaiolMaterial.orgao_id == orgao_id) | (PaiolCustodiaEvento.material_id.is_(None))
        )
    )
    if material_id:
        q = q.filter(PaiolCustodiaEvento.material_id == material_id)
    return q.order_by(PaiolCustodiaEvento.created_at.desc()).limit(limit).all()
