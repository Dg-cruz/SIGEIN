"""Script para sincronizar estados e municípios com a API do IBGE."""

from database import SessionLocal
from services.ibge_service import IbgeSyncError, sync_geografia_completa


def main() -> None:
    db = SessionLocal()
    try:
        print("Sincronizando estados e municípios com o IBGE...")
        resultado = sync_geografia_completa(db)
        print(
            f"[OK] Sincronização concluída. "
            f"Estados alterados/inseridos: {resultado['estados']}. "
            f"Municípios alterados/inseridos: {resultado['municipios']}."
        )
    except IbgeSyncError as exc:
        print(f"[ERRO] {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
