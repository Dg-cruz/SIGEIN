from database import SessionLocal, engine
import models
from models import PerfilEnum, StatusUsuarioEnum
from security import hash_password
from sqlalchemy.exc import IntegrityError
from services.ibge_service import IbgeSyncError, ensure_estados

models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    ensure_estados(db)
    print("[OK] Estados sincronizados com o IBGE.")
except IbgeSyncError as exc:
    print(f"[AVISO] Nao foi possivel sincronizar estados com o IBGE: {exc}")

ADMIN_EMAIL = "admin@sigen.local"
ADMIN_PASSWORD = "1234"
ADMIN_NOME = "Administrador SIGEN"
ADMIN_CPF = "00000000000"

MUNICIPIO_ID = 1
ORGAO_ID = 1
UNIDADE_ID = 1

try:
    existing_user = db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first()

    if existing_user:
        print(f"[AVISO] Usuario admin ja existe (ID: {existing_user.id}, e-mail: {existing_user.email})")
    else:
        admin_user = models.User(
            nome=ADMIN_NOME,
            cpf=ADMIN_CPF,
            email=ADMIN_EMAIL,
            password=hash_password(ADMIN_PASSWORD),
            municipio_id=MUNICIPIO_ID,
            orgao_id=ORGAO_ID,
            unidade_id=UNIDADE_ID,
            perfil=PerfilEnum.MASTER,
            status=StatusUsuarioEnum.ATIVO,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"[OK] Usuario admin criado com sucesso (ID: {admin_user.id})!")
        print(f"     E-mail: {ADMIN_EMAIL}")
        print(f"     Senha:  {ADMIN_PASSWORD}")

except IntegrityError as e:
    db.rollback()
    print(f"[ERRO] Erro de integridade ao criar admin: {e}")
    print("   Verifique se municipio_id, orgao_id e unidade_id existem no banco.")

finally:
    db.close()
