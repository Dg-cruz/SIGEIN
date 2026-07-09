"""Relatórios operacionais e exportação do módulo Paiol."""

import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models import PaiolMaterial, PaiolMovimentacao, PaiolRequisicao, PaiolSaldo
from paiol_constants import STATUS_REQUISICAO_LABELS_STR, StatusRequisicaoPaiol, TIPO_MOVIMENTO_LABELS, TipoMovimentacaoPaiol


def build_relatorios_resumo(db: Session, orgao_id: int) -> dict:
    saldos = (
        db.query(PaiolSaldo)
        .join(PaiolMaterial)
        .filter(PaiolMaterial.orgao_id == orgao_id)
        .count()
    )
    movs = db.query(PaiolMovimentacao).join(PaiolMaterial).filter(PaiolMaterial.orgao_id == orgao_id).count()
    reqs_pendentes = (
        db.query(PaiolRequisicao)
        .filter(
            PaiolRequisicao.orgao_id == orgao_id,
            PaiolRequisicao.status.in_(
                [StatusRequisicaoPaiol.PENDENTE.value, StatusRequisicaoPaiol.APROVADA.value]
            ),
        )
        .count()
    )
    return {
        "saldos_registrados": saldos,
        "movimentacoes_total": movs,
        "requisicoes_abertas": reqs_pendentes,
    }


def export_estoque_csv(db: Session, orgao_id: int) -> str:
    rows = (
        db.query(PaiolSaldo)
        .join(PaiolMaterial)
        .options(
            joinedload(PaiolSaldo.material),
            joinedload(PaiolSaldo.deposito),
            joinedload(PaiolSaldo.localizacao),
        )
        .filter(PaiolMaterial.orgao_id == orgao_id)
        .order_by(PaiolMaterial.nome)
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Material", "Depósito", "Localização", "Quantidade", "Mínimo"])
    for s in rows:
        w.writerow([
            s.material.nome if s.material else "",
            s.deposito.nome if s.deposito else "",
            s.localizacao.codigo if s.localizacao else "",
            s.quantidade,
            s.quantidade_minima or 0,
        ])
    return buf.getvalue()


def export_movimentacoes_csv(db: Session, orgao_id: int) -> str:
    rows = (
        db.query(PaiolMovimentacao)
        .join(PaiolMaterial)
        .options(
            joinedload(PaiolMovimentacao.material),
            joinedload(PaiolMovimentacao.deposito_origem),
            joinedload(PaiolMovimentacao.deposito_destino),
            joinedload(PaiolMovimentacao.user),
        )
        .filter(PaiolMaterial.orgao_id == orgao_id)
        .order_by(PaiolMovimentacao.data.desc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Data", "Tipo", "Material", "Origem", "Destino", "Quantidade", "Usuário", "Observação"])
    for m in rows:
        tipo = TIPO_MOVIMENTO_LABELS.get(TipoMovimentacaoPaiol(m.tipo), m.tipo) if m.tipo in [t.value for t in TipoMovimentacaoPaiol] else m.tipo
        w.writerow([
            m.data.strftime("%d/%m/%Y %H:%M") if m.data else "",
            tipo,
            m.material.nome if m.material else "",
            m.deposito_origem.nome if m.deposito_origem else "",
            m.deposito_destino.nome if m.deposito_destino else "",
            m.quantidade,
            m.user.nome if m.user else "",
            m.observacao or "",
        ])
    return buf.getvalue()


def export_requisicoes_csv(db: Session, orgao_id: int) -> str:
    rows = (
        db.query(PaiolRequisicao)
        .options(joinedload(PaiolRequisicao.solicitante), joinedload(PaiolRequisicao.unidade))
        .filter(PaiolRequisicao.orgao_id == orgao_id)
        .order_by(PaiolRequisicao.created_at.desc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Número", "Status", "Solicitante", "Unidade", "Criada em", "Observação"])
    for r in rows:
        status = STATUS_REQUISICAO_LABELS_STR.get(r.status, r.status)
        w.writerow([
            r.numero,
            status,
            r.solicitante.nome if r.solicitante else "",
            r.unidade.nome if r.unidade else "",
            r.created_at.strftime("%d/%m/%Y %H:%M") if r.created_at else "",
            r.observacao or "",
        ])
    return buf.getvalue()


def csv_filename(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
