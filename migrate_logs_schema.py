"""
Migração: adiciona colunas municipio_id, user_id, tipo, user_agent na tabela logs.

Execute uma vez:
  python migrate_logs_schema.py
"""
from database import engine
from sqlalchemy import text


def coluna_existe(conn, tabela: str, coluna: str) -> bool:
    r = conn.execute(
        text(
            """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :tabela AND column_name = :coluna
        """
        ),
        {"tabela": tabela, "coluna": coluna},
    )
    return r.fetchone() is not None


def main():
    with engine.begin() as conn:
        if not coluna_existe(conn, "logs", "municipio_id"):
            conn.execute(
                text("ALTER TABLE logs ADD COLUMN municipio_id INTEGER REFERENCES municipios(id)")
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_logs_municipio_id ON logs (municipio_id)"))
            print("Coluna logs.municipio_id adicionada.")
        else:
            print("Coluna logs.municipio_id já existe.")

        if not coluna_existe(conn, "logs", "user_id"):
            conn.execute(text("ALTER TABLE logs ADD COLUMN user_id INTEGER REFERENCES users(id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_logs_user_id ON logs (user_id)"))
            print("Coluna logs.user_id adicionada.")
        else:
            print("Coluna logs.user_id já existe.")

        if not coluna_existe(conn, "logs", "tipo"):
            conn.execute(text("ALTER TABLE logs ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'operacional'"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_logs_tipo ON logs (tipo)"))
            print("Coluna logs.tipo adicionada.")
        else:
            print("Coluna logs.tipo já existe.")

        if not coluna_existe(conn, "logs", "user_agent"):
            conn.execute(text("ALTER TABLE logs ADD COLUMN user_agent VARCHAR(500)"))
            print("Coluna logs.user_agent adicionada.")
        else:
            print("Coluna logs.user_agent já existe.")

    print("Migração concluída.")


if __name__ == "__main__":
    main()

