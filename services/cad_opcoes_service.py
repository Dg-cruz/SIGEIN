"""Opções configuráveis dos selects do CAD."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func
from sqlalchemy.orm import Session

from cad_constants import (
    CANAIS,
    MEIOS_EMPREGADOS,
    NATUREZAS,
    PRIORIDADES,
    STATUS_OCORRENCIA,
    TIPOS_NATUREZA,
)
from dependencies import agora_brasilia
from models import CadOpcaoLista

# Tipos de select editáveis em Configurações
TIPOS_OPCAO = (
    ("canal", "Canal de acionamento"),
    ("prioridade", "Prioridade"),
    ("status", "Situação / status"),
    ("tipo_natureza", "Tipo de natureza"),
    ("natureza", "Natureza do fato"),
    ("meio_empregado", "Meio empregado"),
)

TIPOS_OPCAO_LABELS = {k: v for k, v in TIPOS_OPCAO}


def slugify_codigo(texto: str) -> str:
    txt = unicodedata.normalize("NFKD", texto or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9]+", "_", txt)
    return txt.strip("_")[:50] or "opcao"


def ensure_opcoes_municipio(db: Session, municipio_id: int) -> None:
    """Garante opções padrão do município (cria as que ainda faltarem)."""
    existentes = {
        (r.tipo, r.codigo)
        for r in db.query(CadOpcaoLista.tipo, CadOpcaoLista.codigo)
        .filter(CadOpcaoLista.municipio_id == municipio_id)
        .all()
    }

    seeds: list[CadOpcaoLista] = []

    def add(tipo, codigo, label, ordem, extra1=None, extra2=None):
        if (tipo, codigo) in existentes:
            return
        seeds.append(
            CadOpcaoLista(
                municipio_id=municipio_id,
                tipo=tipo,
                codigo=codigo,
                label=label,
                ordem=ordem,
                extra1=extra1,
                extra2=extra2,
                ativo=True,
                sistema=True,
            )
        )

    for i, (c, lab) in enumerate(CANAIS):
        add("canal", c, lab, i)
    for i, (c, lab) in enumerate(PRIORIDADES):
        add("prioridade", c, lab, i)
    for i, (c, lab) in enumerate(STATUS_OCORRENCIA):
        add("status", c, lab, i)
    for i, (c, lab) in enumerate(TIPOS_NATUREZA):
        add("tipo_natureza", c, lab, i)
    for i, (c, lab) in enumerate(MEIOS_EMPREGADOS):
        add("meio_empregado", c, lab, i)
    for i, (c, nome, grupo, tipo) in enumerate(NATUREZAS):
        add("natureza", c, nome, i, extra1=grupo, extra2=tipo)

    if seeds:
        db.add_all(seeds)
        db.commit()


def listar_opcoes(
    db: Session,
    municipio_id: int,
    tipo: str | None = None,
    *,
    apenas_ativos: bool = True,
) -> list[CadOpcaoLista]:
    ensure_opcoes_municipio(db, municipio_id)
    q = db.query(CadOpcaoLista).filter(CadOpcaoLista.municipio_id == municipio_id)
    if tipo:
        q = q.filter(CadOpcaoLista.tipo == tipo)
    if apenas_ativos:
        q = q.filter(CadOpcaoLista.ativo.is_(True))
    # Selects e listagens em ordem alfabética pelo nome (case-insensitive)
    return q.order_by(CadOpcaoLista.tipo, func.lower(CadOpcaoLista.label)).all()


def pairs_opcao(db: Session, municipio_id: int, tipo: str) -> list[tuple[str, str]]:
    return [(o.codigo, o.label) for o in listar_opcoes(db, municipio_id, tipo)]


def labels_opcao(db: Session, municipio_id: int, tipo: str) -> dict[str, str]:
    return dict(pairs_opcao(db, municipio_id, tipo))


def naturezas_tuples(db: Session, municipio_id: int) -> list[tuple]:
    rows = listar_opcoes(db, municipio_id, "natureza")
    return [
        (o.codigo, o.label, o.extra1 or "Diversos", o.extra2 or "atipica")
        for o in rows
    ]


def resolver_natureza_db(db: Session, municipio_id: int, codigo: str) -> dict:
    ensure_opcoes_municipio(db, municipio_id)
    row = (
        db.query(CadOpcaoLista)
        .filter(
            CadOpcaoLista.municipio_id == municipio_id,
            CadOpcaoLista.tipo == "natureza",
            CadOpcaoLista.codigo == codigo,
            CadOpcaoLista.ativo.is_(True),
        )
        .first()
    )
    if row:
        return {
            "codigo": row.codigo,
            "nome": row.label,
            "grupo": row.extra1 or "Diversos",
            "tipo": row.extra2 or "atipica",
        }
    # fallback
    from cad_constants import NATUREZA_POR_CODIGO

    meta = NATUREZA_POR_CODIGO.get("outro", {"nome": "Outra natureza", "grupo": "Diversos", "tipo": "atipica"})
    return {"codigo": "outro", "nome": meta["nome"], "grupo": meta["grupo"], "tipo": meta["tipo"]}


def catalogos_formulario(db: Session, municipio_id: int) -> dict:
    ensure_opcoes_municipio(db, municipio_id)
    canais = pairs_opcao(db, municipio_id, "canal")
    prioridades = pairs_opcao(db, municipio_id, "prioridade")
    status_list = pairs_opcao(db, municipio_id, "status")
    tipos_natureza = pairs_opcao(db, municipio_id, "tipo_natureza")
    meios = pairs_opcao(db, municipio_id, "meio_empregado")
    naturezas = naturezas_tuples(db, municipio_id)
    return {
        "canais": canais,
        "prioridades": prioridades,
        "status_list": status_list,
        "tipos_natureza": tipos_natureza,
        "naturezas": naturezas,
        "meios": meios,
        "prioridade_labels": dict(prioridades),
        "status_labels": dict(status_list),
        "canal_labels": dict(canais),
        "tipo_natureza_labels": dict(tipos_natureza),
        "meio_labels": dict(meios),
    }


def criar_opcao(
    db: Session,
    *,
    municipio_id: int,
    tipo: str,
    label: str,
    codigo: str | None = None,
    extra1: str | None = None,
    extra2: str | None = None,
    ativo: bool = True,
) -> CadOpcaoLista:
    if tipo not in TIPOS_OPCAO_LABELS:
        raise ValueError("Tipo de lista inválido.")
    label = (label or "").strip()
    if not label:
        raise ValueError("Informe o nome da opção.")
    codigo = (codigo or "").strip() or slugify_codigo(label)
    codigo = slugify_codigo(codigo) if not re.match(r"^[a-z0-9_\-]+$", codigo) else codigo

    dup = (
        db.query(CadOpcaoLista)
        .filter(
            CadOpcaoLista.municipio_id == municipio_id,
            CadOpcaoLista.tipo == tipo,
            CadOpcaoLista.codigo == codigo,
        )
        .first()
    )
    if dup:
        raise ValueError("Já existe uma opção com este código neste tipo.")

    max_ordem = (
        db.query(CadOpcaoLista)
        .filter(CadOpcaoLista.municipio_id == municipio_id, CadOpcaoLista.tipo == tipo)
        .count()
    )
    row = CadOpcaoLista(
        municipio_id=municipio_id,
        tipo=tipo,
        codigo=codigo,
        label=label,
        extra1=(extra1 or "").strip() or None,
        extra2=(extra2 or "").strip() or None,
        ordem=max_ordem,
        ativo=ativo,
        sistema=False,
        created_at=agora_brasilia(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def atualizar_opcao(
    db: Session,
    *,
    municipio_id: int,
    opcao_id: int,
    label: str,
    extra1: str | None = None,
    extra2: str | None = None,
    ativo: bool = True,
    ordem: int | None = None,
) -> CadOpcaoLista:
    row = (
        db.query(CadOpcaoLista)
        .filter(
            CadOpcaoLista.id == opcao_id,
            CadOpcaoLista.municipio_id == municipio_id,
        )
        .first()
    )
    if not row:
        raise ValueError("Opção não encontrada.")
    label = (label or "").strip()
    if not label:
        raise ValueError("Informe o nome da opção.")
    row.label = label
    row.extra1 = (extra1 or "").strip() or None
    row.extra2 = (extra2 or "").strip() or None
    row.ativo = bool(ativo)
    if ordem is not None:
        row.ordem = int(ordem)
    row.updated_at = agora_brasilia()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def excluir_opcao(db: Session, municipio_id: int, opcao_id: int) -> None:
    row = (
        db.query(CadOpcaoLista)
        .filter(
            CadOpcaoLista.id == opcao_id,
            CadOpcaoLista.municipio_id == municipio_id,
        )
        .first()
    )
    if not row:
        raise ValueError("Opção não encontrada.")
    if row.sistema:
        # opções de sistema apenas desativam
        row.ativo = False
        row.updated_at = agora_brasilia()
        db.add(row)
        db.commit()
        return
    db.delete(row)
    db.commit()
