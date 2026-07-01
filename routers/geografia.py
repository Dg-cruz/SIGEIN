from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Estado, Municipio, PerfilEnum, User
from templating import templates

router = APIRouter(tags=["Geografia IBGE"])


def _is_master(user: User) -> bool:
    return user._perfil_valor() == PerfilEnum.MASTER.value


@router.get("/admin/geografia")
def pagina_geografia_ibge(
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()
    if not user_obj or not _is_master(user_obj):
        return HTMLResponse("Acesso negado. Apenas MASTER.", status_code=403)

    return templates.TemplateResponse(
        "geografia_ibge.html",
        {
            "request": request,
            "total_estados": db.query(Estado).count(),
            "total_municipios": db.query(Municipio).count(),
            "hide_app_header": True,
        },
    )
