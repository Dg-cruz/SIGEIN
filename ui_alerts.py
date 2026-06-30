"""Respostas HTML padronizadas com alertas SIGEN (SweetAlert2)."""

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

from templating import templates

_VALID_ICONS = frozenset({"error", "warning", "info", "success"})


def _is_ajax(request: Request) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def alert_back(
    request: Request,
    message: str,
    icon: str = "error",
    status_code: int = 400,
) -> Response:
    """Exibe modal SIGEN na própria tela (AJAX) ou via flash + redirect (fallback)."""
    icon_key = icon if icon in _VALID_ICONS else "error"
    text = (message or "").strip()

    if _is_ajax(request):
        return JSONResponse(
            {"ok": False, "alert": True, "message": text, "icon": icon_key},
            status_code=status_code,
        )

    referer = request.headers.get("referer") or "/dashboard"
    request.session["sigen_alert"] = {"message": text, "icon": icon_key}
    return RedirectResponse(url=referer, status_code=303)
