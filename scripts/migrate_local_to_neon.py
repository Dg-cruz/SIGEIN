"""Replica dados do PostgreSQL local para o banco Neon (somente dados)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LOCAL = "postgresql://postgres:1234@localhost:5432/sigein"

# Ordem respeitando chaves estrangeiras (pais antes dos filhos).
TABLES_ORDER = [
    "estados",
    "equipment_types",
    "categories",
    "brands",
    "brand_equipment_types",
    "equipment_states",
    "grupos",
    "municipios",
    "assuntos",
    "subassuntos",
    "orgaos",
    "unidades",
    "units",
    "users",
    "requerentes",
    "products",
    "product_attachments",
    "items",
    "stock",
    "movements",
    "logs",
    "processos",
    "processo_assinantes",
    "tramites",
    "circulares",
    "circular_destinatarios",
    "segem_itens",
    "produtos_segem",
    "segem_itens_produtos",
]


def connect(url: str):
    return psycopg2.connect(url)


def ensure_schema(remote_url: str) -> None:
    os.environ.setdefault("DATABASE_URL", remote_url)
    from database import Base, engine
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def list_public_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
        return [row[0] for row in cur.fetchall()]


def table_exists(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table,),
        )
        return bool(cur.fetchone()[0])


def truncate_remote(conn, tables: list[str]) -> None:
    if not tables:
        return
    with conn.cursor() as cur:
        identifiers = sql.SQL(", ").join(sql.Identifier(t) for t in tables)
        cur.execute(
            sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(identifiers)
        )
    conn.commit()


def copy_table(local_conn, remote_conn, table: str) -> int:
    with local_conn.cursor() as lcur:
        lcur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
        rows = lcur.fetchall()
        columns = [desc[0] for desc in lcur.description]

    if not rows:
        return 0

    insert_sql = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(col) for col in columns),
    )

    with remote_conn.cursor() as rcur:
        execute_values(rcur, insert_sql.as_string(remote_conn), rows, page_size=500)

    return len(rows)


def reset_sequences(remote_conn, tables: list[str]) -> None:
    with remote_conn.cursor() as cur:
        for table in tables:
            cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
            row = cur.fetchone()
            if not row or not row[0]:
                continue
            cur.execute(
                sql.SQL(
                    "SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {}), 1), true)"
                ).format(sql.Identifier(table)),
                (row[0],),
            )
    remote_conn.commit()


def dump_sql(local_url: str, output: Path) -> None:
    """Gera arquivo SQL (somente dados) para importar no Neon via psql."""
    conn = connect(local_url)
    try:
        tables = list_public_tables(conn)
        # Apenas tabelas definidas em models.py (que existem no schema do Neon).
        # Tabelas legadas locais (ex.: equipments) são ignoradas.
        ordered = [t for t in TABLES_ORDER if t in tables]
        ignoradas = sorted(set(tables) - set(ordered))
        if ignoradas:
            print(f"[AVISO] Tabelas ignoradas (fora do schema atual): {', '.join(ignoradas)}")

        lines = ["BEGIN;"]

        if ordered:
            table_list = ", ".join(f'"{t}"' for t in ordered)
            lines.append(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;")

        with conn.cursor() as cur:
            for table in ordered:
                cur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                if not rows:
                    continue

                col_sql = ", ".join(f'"{c}"' for c in columns)
                lines.append(f"\n-- {table} ({len(rows)} registros)")
                for row in rows:
                    placeholders = ", ".join(
                        cur.mogrify("%s", (value,)).decode("utf-8") for value in row
                    )
                    lines.append(f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders});')

        lines.append("COMMIT;")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines), encoding="utf-8")
        print(f"[OK] Dump gerado em: {output}")
    finally:
        conn.close()


def migrate(local_url: str, remote_url: str, skip_schema: bool = False) -> None:
    print("Conectando ao banco local...")
    local_conn = connect(local_url)

    print("Conectando ao Neon...")
    remote_conn = connect(remote_url)

    try:
        if not skip_schema:
            print("Garantindo schema no Neon...")
            ensure_schema(remote_url)

        local_tables = set(list_public_tables(local_conn))
        remote_tables = set(list_public_tables(remote_conn))
        ordered = [t for t in TABLES_ORDER if t in local_tables and t in remote_tables]
        extras = sorted((local_tables & remote_tables) - set(ordered))
        ordered.extend(extras)

        print(f"Tabelas a replicar: {len(ordered)}")
        truncate_remote(remote_conn, list(reversed(ordered)))

        total_rows = 0
        for table in ordered:
            rows = copy_table(local_conn, remote_conn, table)
            remote_conn.commit()
            total_rows += rows
            print(f"  {table}: {rows} registro(s)")

        reset_sequences(remote_conn, ordered)
        print(f"\n[OK] Migração concluída. {total_rows} registro(s) copiados.")
    finally:
        local_conn.close()
        remote_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replica dados local -> Neon")
    parser.add_argument("--local", default=os.getenv("LOCAL_DATABASE_URL", DEFAULT_LOCAL))
    parser.add_argument("--remote", default=os.getenv("NEON_DATABASE_URL"))
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Não executa create_all no destino",
    )
    parser.add_argument(
        "--dump",
        default="",
        help="Somente gera arquivo .sql local (ex.: backups/sigein_data.sql)",
    )
    args = parser.parse_args()

    if args.dump:
        dump_sql(args.local, Path(args.dump))
        return

    if not args.remote:
        print("[ERRO] Informe --remote ou a variável NEON_DATABASE_URL.")
        sys.exit(1)

    migrate(args.local, args.remote, skip_schema=args.skip_schema)


if __name__ == "__main__":
    main()
