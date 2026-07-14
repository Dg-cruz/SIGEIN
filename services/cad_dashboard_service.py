"""Métricas e widgets personalizados do dashboard CAD."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from cad_constants import (
    CAD_DASHBOARD_DEFAULT_KEYS,
    CAD_DASHBOARD_WIDGETS,
    CAD_DASHBOARD_WIDGETS_BY_KEY,
)
from dependencies import agora_brasilia
from models import CadDashboardWidget, CadOcorrencia


def _inicio_dia(agora: datetime) -> datetime:
    return datetime.combine(agora.date(), time.min)


def _abertas_clause():
    return ~CadOcorrencia.status.in_(("encerrada", "cancelada"))


def build_cad_metrics(db: Session, municipio_id: int) -> dict:
    agora = agora_brasilia()
    inicio = _inicio_dia(agora)
    base = db.query(CadOcorrencia).filter(CadOcorrencia.municipio_id == municipio_id)

    def count_filter(*clauses):
        q = base
        for c in clauses:
            q = q.filter(c)
        return q.count()

    metrics = {
        "total_hoje": count_filter(CadOcorrencia.data_hora_registro >= inicio),
        "em_atendimento": count_filter(CadOcorrencia.status == "em_atendimento"),
        "aguardando_despacho": count_filter(CadOcorrencia.status == "aguardando_despacho"),
        "empenhadas": count_filter(
            CadOcorrencia.status.in_(("empenhada", "em_atendimento_campo"))
        ),
        "emergencia": count_filter(
            CadOcorrencia.prioridade == "emergencia",
            _abertas_clause(),
        ),
        "urgentes": count_filter(
            CadOcorrencia.prioridade == "urgente",
            _abertas_clause(),
        ),
        "encerradas_hoje": count_filter(
            CadOcorrencia.status == "encerrada",
            CadOcorrencia.updated_at >= inicio,
        ),
        "total_abertas": count_filter(_abertas_clause()),
        "canal_153": count_filter(
            CadOcorrencia.canal == "153",
            CadOcorrencia.data_hora_registro >= inicio,
        ),
        "tipicas_hoje": count_filter(
            CadOcorrencia.tipo_natureza == "tipica",
            CadOcorrencia.data_hora_registro >= inicio,
        ),
        "atipicas_hoje": count_filter(
            CadOcorrencia.tipo_natureza == "atipica",
            CadOcorrencia.data_hora_registro >= inicio,
        ),
        "sem_endereco": count_filter(
            _abertas_clause(),
            or_(CadOcorrencia.logradouro.is_(None), CadOcorrencia.logradouro == ""),
        ),
        "updated_at": agora.strftime("%d/%m/%Y %H:%M"),
    }

    recentes = (
        base.options(joinedload(CadOcorrencia.criador))
        .order_by(CadOcorrencia.data_hora_registro.desc())
        .limit(8)
        .all()
    )
    metrics["recentes"] = recentes

    por_status = (
        db.query(CadOcorrencia.status, func.count(CadOcorrencia.id))
        .filter(CadOcorrencia.municipio_id == municipio_id, _abertas_clause())
        .group_by(CadOcorrencia.status)
        .all()
    )
    metrics["por_status"] = {s: c for s, c in por_status}

    por_prioridade = (
        db.query(CadOcorrencia.prioridade, func.count(CadOcorrencia.id))
        .filter(CadOcorrencia.municipio_id == municipio_id, _abertas_clause())
        .group_by(CadOcorrencia.prioridade)
        .all()
    )
    metrics["por_prioridade"] = {p: c for p, c in por_prioridade}

    return metrics


def _resolve_widget(row: CadDashboardWidget, metrics: dict) -> dict | None:
    meta = CAD_DASHBOARD_WIDGETS_BY_KEY.get(row.widget_key)
    if not meta:
        return None
    return {
        "id": row.id,
        "widget_key": row.widget_key,
        "sort_order": row.sort_order,
        "value": metrics.get(row.widget_key, 0),
        **meta,
    }


def ensure_default_widgets(db: Session, user_id: int) -> None:
    exists = (
        db.query(CadDashboardWidget.id)
        .filter(CadDashboardWidget.user_id == user_id)
        .first()
    )
    if exists:
        return
    for i, key in enumerate(CAD_DASHBOARD_DEFAULT_KEYS):
        db.add(
            CadDashboardWidget(user_id=user_id, widget_key=key, sort_order=i)
        )
    db.commit()


def list_user_widgets(db: Session, user_id: int, metrics: dict) -> list[dict]:
    ensure_default_widgets(db, user_id)
    rows = (
        db.query(CadDashboardWidget)
        .filter(CadDashboardWidget.user_id == user_id)
        .order_by(CadDashboardWidget.sort_order, CadDashboardWidget.id)
        .all()
    )
    out = []
    for row in rows:
        resolved = _resolve_widget(row, metrics)
        if resolved:
            out.append(resolved)
    return out


def list_available_widgets(db: Session, user_id: int) -> list[dict]:
    used = {
        r.widget_key
        for r in db.query(CadDashboardWidget.widget_key)
        .filter(CadDashboardWidget.user_id == user_id)
        .all()
    }
    return [w for w in CAD_DASHBOARD_WIDGETS if w["key"] not in used]


def add_widget(db: Session, user_id: int, widget_key: str) -> dict:
    if widget_key not in CAD_DASHBOARD_WIDGETS_BY_KEY:
        raise ValueError("Widget inválido")
    exists = (
        db.query(CadDashboardWidget)
        .filter(
            CadDashboardWidget.user_id == user_id,
            CadDashboardWidget.widget_key == widget_key,
        )
        .first()
    )
    if exists:
        raise ValueError("Widget já adicionado")
    count = (
        db.query(CadDashboardWidget)
        .filter(CadDashboardWidget.user_id == user_id)
        .count()
    )
    row = CadDashboardWidget(user_id=user_id, widget_key=widget_key, sort_order=count)
    db.add(row)
    db.commit()
    db.refresh(row)
    metrics = {widget_key: 0}
    resolved = _resolve_widget(row, metrics)
    if not resolved:
        raise ValueError("Widget inválido")
    return resolved


def remove_widget(db: Session, user_id: int, widget_id: int) -> bool:
    row = (
        db.query(CadDashboardWidget)
        .filter(
            CadDashboardWidget.id == widget_id,
            CadDashboardWidget.user_id == user_id,
        )
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
