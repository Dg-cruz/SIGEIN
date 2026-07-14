"""Serviços do CAD — ocorrências."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime

from sqlalchemy.orm import Session

from cad_constants import NATUREZA_POR_CODIGO
from dependencies import agora_brasilia
from models import CadOcorrencia


def gerar_protocolo(db: Session, agora: datetime | None = None) -> str:
    agora = agora or agora_brasilia()
    prefix = agora.strftime("%Y%m%d")
    like = f"{prefix}-%"
    count = (
        db.query(CadOcorrencia)
        .filter(CadOcorrencia.protocolo.like(like))
        .count()
    )
    return f"{prefix}-{count + 1:04d}"


def resolver_natureza(codigo: str) -> dict:
    meta = NATUREZA_POR_CODIGO.get(codigo) or NATUREZA_POR_CODIGO["outro"]
    return {
        "codigo": codigo if codigo in NATUREZA_POR_CODIGO else "outro",
        "nome": meta["nome"],
        "grupo": meta["grupo"],
        "tipo": meta["tipo"],
    }


def parse_datetime_local(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def buscar_endereco_cep(cep: str) -> dict:
    """Consulta ViaCEP e normaliza resposta para o formulário do CAD."""
    digits = re.sub(r"\D", "", cep or "")
    if len(digits) != 8:
        return {"ok": False, "error": "CEP deve conter 8 dígitos."}

    url = f"https://viacep.com.br/ws/{digits}/json/"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SIGEIN-CAD/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return {"ok": False, "error": "Falha ao consultar o serviço de CEP. Tente novamente."}

    if payload.get("erro"):
        return {"ok": False, "error": "CEP não encontrado."}

    return {
        "ok": True,
        "cep": payload.get("cep") or f"{digits[:5]}-{digits[5:]}",
        "logradouro": payload.get("logradouro") or "",
        "complemento": payload.get("complemento") or "",
        "bairro": payload.get("bairro") or "",
        "cidade": payload.get("localidade") or "",
        "uf": (payload.get("uf") or "").upper(),
        "ibge": payload.get("ibge") or "",
    }
