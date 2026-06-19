# utils.py
from fastapi import Request
from templating import templates

sessions = {}

GUEST_DISPLAY_NAME = "Visitante"

def get_logged_user(request: Request):
    """Retorna o username logado a partir do cookie, ou None se não estiver logado."""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]
    return None

def context_with_user(request: Request, extra_context: dict = None):
    """Retorna contexto para templates incluindo usuário logado."""
    context = {"user": get_logged_user(request)}
    if extra_context:
        context.update(extra_context)
    return context

def get_top_submenu(request: Request):
    """Gera HTML do submenu superior com o nome do usuário logado."""
    display_name = get_logged_user(request) or GUEST_DISPLAY_NAME
    submenu_html = f"""
    <div class="top-submenu" style="text-align: right; padding: 10px 20px; background: #f5f5f5; border-bottom: 1px solid #ccc;">
        Olá, <span class="user-name" style="font-weight:bold;">{display_name}</span>
        | <a href="/logout">Sair</a>
    </div>
    """
    return submenu_html
