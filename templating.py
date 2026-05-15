"""Templates Jinja2 compartilhados (Starlette 1.0 + contexto do usuário)."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from starlette.requests import Request
from starlette.templating import Jinja2Templates as _Jinja2Templates

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

PERFIL_LABELS = {
    "master": "Master",
    "admin_municipal": "Admin Municipal",
    "gestor_estoque": "Gestor de Estoque",
    "gestor_protocolo": "Gestor de Protocolo",
    "gestor_geral": "Gestor Geral",
    "gestor_segem": "Gestor SEGEM",
    "operador": "Operador",
}


def get_logged_user(request: Request):
    return request.session.get("user")


def inject_user_context(request: Request) -> dict[str, Any]:
    email = request.session.get("user")
    nome = request.session.get("user_nome") or email or ""
    primeiro = nome.split()[0] if nome and nome.strip() else ""
    perfil = request.session.get("perfil") or ""

    hora = datetime.now().hour
    if hora < 12:
        saudacao = "Bom dia"
    elif hora < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    return {
        "current_user_email": email,
        "current_user_nome": nome,
        "current_user_primeiro_nome": primeiro,
        "current_user_id": request.session.get("user_id"),
        "current_user_perfil": perfil,
        "current_user_perfil_label": PERFIL_LABELS.get(perfil, perfil),
        "user_saudacao": saudacao,
        "is_logged_in": bool(email),
    }


class Jinja2Templates(_Jinja2Templates):
    def TemplateResponse(
        self,
        name_or_request: Request | str,
        context: dict[str, Any] | str | None = None,
        **kwargs: Any,
    ):
        if isinstance(name_or_request, str):
            template_name = name_or_request
            template_context = dict(context or {})
            request = template_context.pop("request", None)
            if request is None:
                raise ValueError(
                    "TemplateResponse legado exige 'request' no contexto."
                )
            return super().TemplateResponse(
                request,
                template_name,
                template_context or None,
                **kwargs,
            )
        return super().TemplateResponse(name_or_request, context, **kwargs)


templates = Jinja2Templates(directory=TEMPLATE_DIR)
templates.context_processors.append(inject_user_context)
templates.env.globals["get_logged_user"] = get_logged_user
