"""Sincroniza estados e municípios brasileiros com a API pública do IBGE."""

from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.error
import urllib.request

from sqlalchemy.orm import Session

from models import Estado, Municipio

logger = logging.getLogger(__name__)

IBGE_BASE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
REQUEST_TIMEOUT = 60
MAX_RETRIES = 3


class IbgeSyncError(Exception):
    """Erro ao consultar ou processar dados do IBGE."""


def _fetch_json(url: str) -> list | dict:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "SIGEN/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            break

    raise IbgeSyncError(f"Falha ao consultar IBGE ({url}): {last_error}") from last_error


def sync_estados(db: Session) -> int:
    """Importa ou atualiza estados a partir do IBGE. Retorna quantidade alterada."""
    data = _fetch_json(f"{IBGE_BASE}?orderBy=nome")
    if not isinstance(data, list):
        raise IbgeSyncError("Formato inesperado na listagem de estados do IBGE")

    alterados = 0
    for item in data:
        uf = item["sigla"]
        nome = item["nome"]
        estado = db.query(Estado).filter(Estado.uf == uf).first()
        if estado:
            if estado.nome != nome:
                estado.nome = nome
                alterados += 1
        else:
            db.add(Estado(nome=nome, uf=uf))
            alterados += 1

    db.commit()
    return alterados


def sync_municipios_por_estado(db: Session, estado: Estado) -> int:
    """Importa ou atualiza municípios de um estado. Retorna quantidade alterada."""
    data = _fetch_json(f"{IBGE_BASE}/{estado.uf}/municipios?orderBy=nome")
    if not isinstance(data, list):
        raise IbgeSyncError(f"Formato inesperado na listagem de municípios de {estado.uf}")

    alterados = 0
    for item in data:
        codigo_ibge = str(item["id"])
        nome = item["nome"]

        municipio = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
        if municipio:
            changed = False
            if municipio.nome != nome:
                municipio.nome = nome
                changed = True
            if municipio.estado_id != estado.id:
                municipio.estado_id = estado.id
                changed = True
            if changed:
                alterados += 1
            continue

        municipio = (
            db.query(Municipio)
            .filter(
                Municipio.estado_id == estado.id,
                Municipio.nome == nome,
                Municipio.codigo_ibge.is_(None),
            )
            .first()
        )
        if municipio:
            municipio.codigo_ibge = codigo_ibge
            alterados += 1
            continue

        db.add(
            Municipio(
                nome=nome,
                codigo_ibge=codigo_ibge,
                estado_id=estado.id,
                ativo=True,
            )
        )
        alterados += 1

    db.commit()
    return alterados


def sync_todos_municipios(db: Session) -> int:
    """Importa municípios de todos os estados cadastrados."""
    estados = db.query(Estado).order_by(Estado.nome).all()
    total = 0
    for estado in estados:
        try:
            total += sync_municipios_por_estado(db, estado)
        except IbgeSyncError as exc:
            logger.warning("Falha ao sincronizar municípios de %s: %s", estado.uf, exc)
    return total


def sync_geografia_completa(db: Session) -> dict:
    """Sincroniza estados e todos os municípios."""
    estados = sync_estados(db)
    municipios = sync_todos_municipios(db)
    return {"estados": estados, "municipios": municipios}


def ensure_estados(db: Session) -> bool:
    """Garante que a tabela de estados esteja populada."""
    if db.query(Estado).count() > 0:
        return False
    sync_estados(db)
    return True


def ensure_municipios_estado(db: Session, estado_id: int) -> bool:
    """Garante municípios de um estado; sincroniza sob demanda se estiver vazio."""
    total = (
        db.query(Municipio)
        .filter(Municipio.estado_id == estado_id, Municipio.ativo.is_(True))
        .count()
    )
    if total > 0:
        return False

    estado = db.query(Estado).filter(Estado.id == estado_id).first()
    if not estado:
        return False

    sync_municipios_por_estado(db, estado)
    return True
