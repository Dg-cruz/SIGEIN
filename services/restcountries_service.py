"""Integração com REST Countries (v5) para listagem de países."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_API_BASE = "https://api.restcountries.com/countries/v5"
_CACHE_TTL_SECONDS = 60 * 60 * 24
_STATIC_FILE = Path(__file__).resolve().parent.parent / "static" / "data" / "paises.json"
_cache: dict[str, Any] = {"expires_at": 0.0, "paises": []}


def _api_key() -> str:
    return os.getenv("RESTCOUNTRIES_API_KEY", "").strip()


def _nome_pais(item: dict) -> str:
    names = item.get("names") or {}
    native = names.get("native") or {}
    for lang in ("por", "pt", "eng"):
        block = native.get(lang)
        if isinstance(block, dict) and block.get("common"):
            return str(block["common"]).strip()
    common = names.get("common")
    if common:
        return str(common).strip()
    official = names.get("official")
    if official:
        return str(official).strip()
    return ""


def _carregar_paises_estaticos() -> list[dict[str, str]]:
    if not _STATIC_FILE.exists():
        return []
    try:
        data = json.loads(_STATIC_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [p for p in data if isinstance(p, dict) and p.get("value") and p.get("label")]


def _buscar_paises_api() -> list[dict[str, str]]:
    api_key = _api_key()
    if not api_key:
        return []

    url = f"{_API_BASE}?limit=300&response_fields=names"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "SIGEIN/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)

    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []

    vistos: set[str] = set()
    paises: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        nome = _nome_pais(item)
        if not nome or nome in vistos:
            continue
        vistos.add(nome)
        paises.append({"value": nome, "label": nome})

    paises.sort(key=lambda p: p["label"].casefold())
    return paises


def listar_paises() -> list[dict[str, str]]:
    """Retorna países ordenados por nome para uso em selects."""
    agora = time.time()
    if _cache["paises"] and agora < _cache["expires_at"]:
        return list(_cache["paises"])

    paises: list[dict[str, str]] = []
    try:
        paises = _buscar_paises_api()
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError, ValueError):
        paises = []

    if not paises:
        paises = _carregar_paises_estaticos()

    if paises:
        _cache["paises"] = paises
        _cache["expires_at"] = agora + _CACHE_TTL_SECONDS

    return list(paises)
