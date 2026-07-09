"""Métricas e consolidações do módulo Paiol."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from dependencies import agora_brasilia
from models import PaiolMaterial, PaiolMovimentacao, PaiolSaldo


def _status_saldo(quantidade: int, quantidade_minima: int) -> str:
    minimo = quantidade_minima or 0
    if quantidade <= 0:
        return "ZERADO"
    if minimo > 0 and quantidade <= minimo:
        return "CRITICO"
    return "OK"


def build_paiol_dashboard_metrics(db: Session) -> dict:
    total_products = db.query(PaiolMaterial).count()
    critical_products = (
        db.query(PaiolSaldo)
        .filter(PaiolSaldo.quantidade <= PaiolSaldo.quantidade_minima)
        .count()
    )
    zero_stock_products = db.query(PaiolSaldo).filter(PaiolSaldo.quantidade <= 0).count()

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_movements_count = (
        db.query(PaiolMovimentacao)
        .filter(PaiolMovimentacao.data >= seven_days_ago)
        .count()
    )

    critical_stock = []
    saldos = (
        db.query(PaiolSaldo)
        .options(
            joinedload(PaiolSaldo.material),
            joinedload(PaiolSaldo.deposito),
        )
        .all()
    )
    for s in saldos:
        status = _status_saldo(s.quantidade, s.quantidade_minima)
        if status in ("ZERADO", "CRITICO"):
            critical_stock.append(
                {
                    "product_name": s.material.nome if s.material else "—",
                    "unit_name": s.deposito.nome if s.deposito else "—",
                    "quantidade": s.quantidade,
                    "quantidade_minima": s.quantidade_minima,
                    "status": status,
                }
            )

    critical_stock.sort(key=lambda x: (0 if x["status"] == "ZERADO" else 1, x["quantidade"]))

    total_rows = len(saldos) or 1
    stock_ok = max(0, total_rows - critical_products)
    health_percent = round((stock_ok / total_rows) * 100)
    pct_ok = round((stock_ok / total_rows) * 100, 1)
    pct_critical = round((critical_products / total_rows) * 100, 1)
    pct_zero = round((zero_stock_products / total_rows) * 100, 1)

    return {
        "total_products": total_products,
        "critical_products": critical_products,
        "zero_stock_products": zero_stock_products,
        "recent_movements_count": recent_movements_count,
        "critical_stock": critical_stock,
        "health_percent": health_percent,
        "stock_ok": stock_ok,
        "pct_ok": pct_ok,
        "pct_critical": pct_critical,
        "pct_zero": pct_zero,
        "updated_at": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S"),
    }


def build_paiol_alerts(db: Session) -> list[dict]:
    alerts: list[dict] = []
    saldos = (
        db.query(PaiolSaldo)
        .options(
            joinedload(PaiolSaldo.material),
            joinedload(PaiolSaldo.deposito),
        )
        .all()
    )
    for s in saldos:
        status = _status_saldo(s.quantidade, s.quantidade_minima)
        if status not in ("ZERADO", "CRITICO"):
            continue
        alerts.append(
            {
                "produto": s.material.nome if s.material else "—",
                "tipo": s.material.tipo if s.material else "—",
                "unidade": s.deposito.nome if s.deposito else "—",
                "quantidade": s.quantidade,
                "minimo": s.quantidade_minima,
                "status": status,
            }
        )
    alerts.sort(key=lambda x: (0 if x["status"] == "ZERADO" else 1, x["quantidade"]))
    return alerts
