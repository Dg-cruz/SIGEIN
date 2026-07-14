from fastapi import FastAPI
from templating import templates
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware  # ✅ Import no topo
from middleware import AuthRequiredMiddleware
from middleware_audit import AuditMiddleware
from database import Base, engine
import os

# ========================================
# 1. CRIAR APP
# ========================================
app = FastAPI()

# ========================================
# 2. ADICIONAR MIDDLEWARES (ANTES DE TUDO)
# ========================================
SECRET_KEY = os.getenv("SECRET_KEY", "sua-chave-secreta-aqui-mude-em-producao")
IS_VERCEL = os.getenv("VERCEL") == "1"

# Ordem (interno → externo): Auth → Session → Audit
# Na requisição: Audit → Session (popula sessão) → Auth (valida login) → rotas
app.add_middleware(AuthRequiredMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=None,
    same_site="lax",
    https_only=IS_VERCEL,
)

# ✅ MultiTenantMiddleware DEPOIS
#app.add_middleware(MultiTenantMiddleware)

# Auditoria de ações (POST/DELETE etc. sem log explícito no router)
app.add_middleware(AuditMiddleware)

# ========================================
# 3. STATIC FILES
# ========================================
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========================================
# 3.1 FAVICON (compatível com /favicon.ico)
# ========================================
FAVICON_PATH = os.path.join(os.path.dirname(__file__), "static", "favicon.ico")


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
async def favicon():
    return FileResponse(FAVICON_PATH, media_type="image/x-icon")

# ========================================
# 4. TEMPLATES (instância única em templating.py)
# ========================================
app.state.templates = templates

# ========================================
# 5. DATABASE (import models para registrar todas as tabelas)
# ========================================
import models  # noqa: F401 - registra modelos no Base.metadata
if not IS_VERCEL or os.getenv("RUN_DB_MIGRATIONS") == "1":
    Base.metadata.create_all(bind=engine)

    if os.getenv("SYNC_IBGE_ON_STARTUP", "1") == "1":
        from database import SessionLocal
        from services.ibge_service import IbgeSyncError, ensure_estados

        _db = SessionLocal()
        try:
            ensure_estados(_db)
        except IbgeSyncError:
            pass
        finally:
            _db.close()

# ========================================
# 6. ROUTERS (POR ÚLTIMO)
# ========================================
from routers import (
    auth, dashboard, users, units, orgaos, movements, logs, root,
    equipment_types, brands, states, products, stock,
    categories, eprotocolo, api_geografica, geografia, segem, paiol, paiol_cadastro, paiol_estoque,
    paiol_workflow, paiol_seguranca, paiol_relatorios, cad
)

app.include_router(root.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(dashboard.controle_router)
app.include_router(users.router)
app.include_router(units.router)
app.include_router(orgaos.router)
app.include_router(movements.router)
app.include_router(categories.router)
app.include_router(equipment_types.router)
app.include_router(products.router)
app.include_router(brands.router)
app.include_router(states.router)
app.include_router(stock.router)
app.include_router(eprotocolo.router)
app.include_router(api_geografica.router)
app.include_router(geografia.router)
app.include_router(logs.router)
app.include_router(segem.router)
app.include_router(paiol.router)
app.include_router(paiol.legacy_router)
app.include_router(paiol_cadastro.router)
app.include_router(paiol_estoque.router)
app.include_router(paiol_workflow.router)
app.include_router(paiol_seguranca.router)
app.include_router(paiol_relatorios.router)
app.include_router(cad.router)