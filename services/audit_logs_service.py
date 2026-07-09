"""Consulta e formatação de registros de auditoria (logs do sistema)."""

from datetime import datetime, timezone
from typing import List, Optional

import pytz
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Log

TZ_BR = pytz.timezone("America/Sao_Paulo")
PAIOL_LOG_PREFIX = "Paiol:"


def _to_local(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_BR)


def fmt_dt(dt: datetime) -> str:
    local = _to_local(dt)
    return local.strftime("%d/%m/%Y %H:%M:%S") if local else "—"


def tipo_label(tipo: str) -> str:
    labels = {
        "acesso": "Acesso",
        "operacional": "Operacional",
        "sistema": "Sistema",
    }
    return labels.get((tipo or "").lower(), tipo or "Operacional")


def tipo_badge_class(tipo: str) -> str:
    t = (tipo or "").lower()
    if t == "acesso":
        return "logs-badge--acesso"
    if t == "sistema":
        return "logs-badge--sistema"
    return "logs-badge--operacional"


def _base_query(db: Session, *, paiol_only: bool = False):
    q = db.query(Log)
    if paiol_only:
        q = q.filter(Log.acao.ilike(f"{PAIOL_LOG_PREFIX}%"))
    return q


def query_logs(db: Session, *, paiol_only: bool = False, limit: Optional[int] = None) -> List[Log]:
    q = _base_query(db, paiol_only=paiol_only).order_by(Log.data_hora.desc())
    if limit:
        q = q.limit(limit)
    return q.all()


def build_log_rows(logs: List[Log]) -> List[dict]:
    rows = []
    for log in logs:
        rows.append({
            "id": log.id,
            "data_hora": fmt_dt(log.data_hora),
            "data_sort": log.data_hora.isoformat() if log.data_hora else "",
            "usuario": log.usuario or "—",
            "tipo": log.tipo or "operacional",
            "tipo_label": tipo_label(log.tipo),
            "tipo_class": tipo_badge_class(log.tipo),
            "ip": log.ip or "—",
            "acao": log.acao or "—",
            "user_agent": (log.user_agent or "—")[:80],
        })
    return rows


def stats(db: Session, *, paiol_only: bool = False) -> dict:
    base = _base_query(db, paiol_only=paiol_only)
    total = base.with_entities(func.count(Log.id)).scalar() or 0
    usuarios_ativos = (
        base.with_entities(func.count(func.distinct(Log.usuario)))
        .filter(Log.usuario.isnot(None), Log.usuario != "")
        .scalar()
        or 0
    )
    acesso = base.filter(Log.tipo == "acesso").with_entities(func.count(Log.id)).scalar() or 0
    operacional = base.filter(Log.tipo == "operacional").with_entities(func.count(Log.id)).scalar() or 0
    sistema = base.filter(Log.tipo == "sistema").with_entities(func.count(Log.id)).scalar() or 0

    hoje = datetime.now(TZ_BR).date()
    logs_hoje = 0
    for dt, in base.with_entities(Log.data_hora).all():
        if dt and _to_local(dt).date() == hoje:
            logs_hoje += 1

    return {
        "total": total,
        "hoje": logs_hoje,
        "usuarios_ativos": usuarios_ativos,
        "acesso": acesso,
        "operacional": operacional,
        "sistema": sistema,
    }


def log_list_template_context(db: Session, user: str, request, *, paiol_only: bool = False) -> dict:
    logs = query_logs(db, paiol_only=paiol_only)
    log_rows = build_log_rows(logs)
    log_stats = stats(db, paiol_only=paiol_only)
    usuarios = sorted({r["usuario"] for r in log_rows if r["usuario"] != "—"})
    tipos = sorted({r["tipo_label"] for r in log_rows})
    ctx = {
        "request": request,
        "logs": log_rows,
        "stats": log_stats,
        "usuarios": usuarios,
        "tipos": tipos,
        "user": user,
        "hide_app_header": True,
    }
    if paiol_only:
        ctx.update({
            "logs_title": "Logs do Paiol",
            "logs_subtitle": "Auditoria das operações do módulo Paiol (mesmo registro de /logs/).",
            "show_exports": False,
            "back_url": "/paiol/dashboard",
            "panel_title": "Registros do módulo Paiol",
            "paiol_logs": True,
        })
    return ctx
