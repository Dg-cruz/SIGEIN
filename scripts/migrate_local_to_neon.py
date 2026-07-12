"""Replica dados do PostgreSQL local para o banco Neon (somente dados)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LOCAL = "postgresql://postgres:1234@localhost:5432/sigein"

# Colunas UNIQUE (além de id) — evita INSERT duplicado no dump (ex.: brands.nome).
UNIQUE_DEDUPE_COLUMNS = {
    "brands": "nome",
    "categories": "nome",
    "equipment_states": "nome",
    "estados": "uf",
    "equipment_types": "nome",
    "grupos": "nome",
}

# Ordem respeitando chaves estrangeiras (pais antes dos filhos).
TABLES_ORDER = [
    "estados",
    "categories",
    "equipment_types",
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
    # Paiol
    "paiol_classes_material",
    "paiol_fabricantes",
    "paiol_fornecedores",
    "paiol_tipos_material",
    "paiol_municoes",
    "paiol_depositos",
    "paiol_localizacoes",
    "paiol_materiais",
    "paiol_lotes",
    "paiol_itens",
    "paiol_saldos",
    "paiol_requisicoes",
    "paiol_requisicao_itens",
    "paiol_movimentacoes",
    "paiol_usuarios_autorizados",
    "paiol_custodia_eventos",
    "paiol_dashboard_atalhos",
    "paiol_assinaturas",
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


def sql_literal(cur, value):
    """Converte valor Python para literal SQL seguro (inclui JSON/dict)."""
    if isinstance(value, (dict, list)):
        value = Json(value)
    return cur.mogrify("%s", (value,)).decode("utf-8")


def model_columns(table: str) -> set[str] | None:
    """Colunas do schema SQLAlchemy (Neon). None = tabela fora do model."""
    try:
        from database import Base
        import models  # noqa: F401
    except Exception:
        return None
    meta = Base.metadata.tables.get(table)
    if meta is None:
        return None
    return {c.name for c in meta.columns}


def dump_sql(local_url: str, output: Path) -> None:
    """Gera arquivo SQL (somente dados) para importar no Neon via psql."""
    conn = connect(local_url)
    try:
        tables = list_public_tables(conn)
        # Apenas tabelas definidas em models.py (que existem no schema do Neon).
        # Tabelas legadas locais (ex.: equipments) são ignoradas.
        ordered = [t for t in TABLES_ORDER if t in tables]
        extras = sorted(set(tables) - set(ordered) - {"equipments", "processo_movimentacoes"})
        if extras:
            print(f"[AVISO] Tabelas extras incluídas ao final: {', '.join(extras)}")
            ordered.extend(extras)
        ignoradas = sorted(set(tables) - set(ordered))
        if ignoradas:
            print(f"[AVISO] Tabelas ignoradas (legado): {', '.join(ignoradas)}")

        lines: list[str] = []
        # Mapa de IDs removidos por dedupe: {tabela: {old_id: kept_id}}
        id_remap: dict[str, dict[int, int]] = {}

        with conn.cursor() as cur:
            table_rows: dict[str, tuple[list[str], list]] = {}
            for table in ordered:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = 'id'
                    """,
                    (table,),
                )
                has_id = cur.fetchone() is not None
                if has_id:
                    cur.execute(
                        sql.SQL("SELECT * FROM {} ORDER BY id").format(
                            sql.Identifier(table)
                        )
                    )
                else:
                    cur.execute(
                        sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
                    )
                rows = list(cur.fetchall())
                columns = [desc[0] for desc in cur.description]
                if not rows:
                    table_rows[table] = (columns, [])
                    continue

                # Remove colunas legadas do banco local que nao existem no schema Neon.
                allowed = model_columns(table)
                if allowed is not None:
                    keep_idx = [i for i, c in enumerate(columns) if c in allowed]
                    dropped = [c for c in columns if c not in allowed]
                    if dropped:
                        print(
                            f"[AVISO] {table}: colunas ignoradas (fora do model): "
                            f"{', '.join(dropped)}"
                        )
                    columns = [columns[i] for i in keep_idx]
                    rows = [[row[i] for i in keep_idx] for row in rows]

                dedupe_col = UNIQUE_DEDUPE_COLUMNS.get(table)
                if dedupe_col and dedupe_col in columns and "id" in columns:
                    id_idx = columns.index("id")
                    val_idx = columns.index(dedupe_col)
                    seen: dict = {}
                    filtered = []
                    remap: dict[int, int] = {}
                    skipped = 0
                    for row in rows:
                        row = list(row)
                        key = row[val_idx]
                        key_norm = (
                            key.strip().casefold()
                            if isinstance(key, str)
                            else key
                        )
                        row_id = row[id_idx]
                        if key_norm in seen:
                            remap[row_id] = seen[key_norm]
                            skipped += 1
                            continue
                        seen[key_norm] = row_id
                        filtered.append(row)
                    if skipped:
                        print(
                            f"[AVISO] {table}: {skipped} registro(s) duplicado(s) "
                            f"em '{dedupe_col}' ignorados no dump."
                        )
                        id_remap[table] = remap
                    rows = filtered

                table_rows[table] = (columns, rows)

            # Remapeia FKs conhecidas após dedupe de brands/categories/etc.
            fk_remap_columns = {
                "brand_equipment_types": [("brand_id", "brands"), ("type_id", "equipment_types")],
                "products": [
                    ("brand_id", "brands"),
                    ("type_id", "equipment_types"),
                    ("category_id", "categories"),
                ],
                "equipment_types": [("category_id", "categories")],
            }
            for table, fks in fk_remap_columns.items():
                if table not in table_rows:
                    continue
                columns, rows = table_rows[table]
                if not rows:
                    continue
                new_rows = []
                seen_pairs: set = set()
                for row in rows:
                    row = list(row)
                    skip = False
                    for col_name, parent in fks:
                        if col_name not in columns or parent not in id_remap:
                            continue
                        col_idx = columns.index(col_name)
                        old_val = row[col_idx]
                        if old_val in id_remap[parent]:
                            row[col_idx] = id_remap[parent][old_val]
                    # dedupe brand_equipment_types PK composed
                    if table == "brand_equipment_types":
                        b_idx = columns.index("brand_id")
                        t_idx = columns.index("type_id")
                        pair = (row[b_idx], row[t_idx])
                        if pair in seen_pairs:
                            skip = True
                        else:
                            seen_pairs.add(pair)
                    if not skip:
                        new_rows.append(row)
                table_rows[table] = (columns, new_rows)

            nonempty = [t for t in ordered if table_rows.get(t, ([], []))[1]]
            if nonempty:
                table_list = ", ".join(f'"{t}"' for t in nonempty)
                lines.append(
                    f'TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;'
                )

            for table in ordered:
                columns, rows = table_rows.get(table, ([], []))
                if not rows:
                    continue
                col_sql = ", ".join(f'"{c}"' for c in columns)
                lines.append(f"\n-- {table} ({len(rows)} registros)")
                for row in rows:
                    placeholders = ", ".join(sql_literal(cur, value) for value in row)
                    conflict = ""
                    if "id" in columns:
                        conflict = ' ON CONFLICT ("id") DO NOTHING'
                    elif table == "brand_equipment_types":
                        conflict = (
                            ' ON CONFLICT ("brand_id", "type_id") DO NOTHING'
                        )
                    lines.append(
                        f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders}){conflict};'
                    )

        output.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "-- SIGEIN dados para Neon\n"
            "-- 1) Rode backups/sigein_schema.sql antes\n"
            "-- 2) Rode este arquivo por completo\n\n"
        )
        output.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
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
