"""Auditoria padronizada do módulo Paiol no log global (/logs/)."""

from fastapi import Request
from sqlalchemy.orm import Session

from dependencies import registrar_log
from services.audit_logs_service import PAIOL_LOG_PREFIX


def log_paiol(db: Session, user: str, request: Request | None, acao: str) -> None:
    """Registra ação do Paiol no log da aplicação com prefixo 'Paiol:'."""
    text = acao if acao.startswith(PAIOL_LOG_PREFIX) else f"{PAIOL_LOG_PREFIX} {acao}"
    registrar_log(db, usuario=user, acao=text[:255], request=request)
