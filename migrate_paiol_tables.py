"""Cria tabelas do módulo Paiol e dados iniciais de cadastro."""

from database import Base, SessionLocal, engine

import models  # noqa: F401
from models import PaiolClasseMaterial
from paiol_constants import TipoMaterialPaiol

TABLES = [
    "paiol_classes_material",
    "paiol_tipos_material",
    "paiol_municoes",
    "paiol_fabricantes",
    "paiol_fornecedores",
    "paiol_depositos",
    "paiol_localizacoes",
    "paiol_materiais",
    "paiol_lotes",
    "paiol_itens",
    "paiol_saldos",
    "paiol_usuarios_autorizados",
    "paiol_custodia_eventos",
    "paiol_dashboard_atalhos",
    "paiol_requisicoes",
    "paiol_requisicao_itens",
    "paiol_assinaturas",
    "paiol_movimentacoes",
]

SEED_CLASSES = [
    ("ARMA", "Armas de fogo", "Material bélico controlado por série", "A"),
    ("MUN-01", "Munição de uso restrito", "Munições", "B"),
    ("EXP-01", "Explosivos e detonantes", "Explosivos", "C"),
    ("ACE-01", "Acessórios bélicos", "Coletes, coldres e similares", "D"),
]


def create_tables():
    for name in TABLES:
        Base.metadata.tables[name].create(bind=engine, checkfirst=True)
    print("Tabelas criadas/verificadas:", ", ".join(TABLES))
    _ensure_movimentacao_requisicao_column()
    _ensure_tipo_material_detalhes_column()
    _ensure_municao_columns()


def _ensure_municao_columns():
    """Atualiza tabela paiol_municoes em bancos já existentes."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "paiol_municoes" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("paiol_municoes")}
    alters = []
    if "nome_comercial" not in cols:
        alters.append("ADD COLUMN nome_comercial VARCHAR(300)")
    if "fabricante_marca" not in cols:
        alters.append("ADD COLUMN fabricante_marca VARCHAR(200)")
    if "fabricante_id" not in cols:
        alters.append("ADD COLUMN fabricante_id INTEGER REFERENCES paiol_fabricantes(id)")
    if "quantidade_tipo" not in cols:
        alters.append("ADD COLUMN quantidade_tipo VARCHAR(20)")
    if "quantidade_valor" not in cols:
        alters.append("ADD COLUMN quantidade_valor INTEGER")
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(f"ALTER TABLE paiol_municoes {stmt}"))
        if "nome_comercial" in cols or alters:
            conn.execute(
                text(
                    "UPDATE paiol_municoes SET nome_comercial = COALESCE(nome_comercial, descricao, calibre) "
                    "WHERE nome_comercial IS NULL OR nome_comercial = ''"
                )
            )
        conn.execute(
            text("ALTER TABLE paiol_municoes DROP CONSTRAINT IF EXISTS paiol_municoes_calibre_key")
        )
    if alters:
        print("Colunas paiol_municoes atualizadas: OK")


def _ensure_tipo_material_detalhes_column():
    """Adiciona coluna detalhes (JSON) em bancos já existentes."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "paiol_tipos_material" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("paiol_tipos_material")}
    if "detalhes" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE paiol_tipos_material ADD COLUMN detalhes JSONB"))
    print("Coluna paiol_tipos_material.detalhes: OK")


def _ensure_movimentacao_requisicao_column():
    """Adiciona coluna requisicao_id em bancos já existentes."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "paiol_movimentacoes" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("paiol_movimentacoes")}
    if "requisicao_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE paiol_movimentacoes ADD COLUMN requisicao_id INTEGER "
                "REFERENCES paiol_requisicoes(id)"
            )
        )
    print("Coluna paiol_movimentacoes.requisicao_id: OK")


def seed_classes(db):
    for codigo, nome, descricao, grupo in SEED_CLASSES:
        exists = db.query(PaiolClasseMaterial).filter(PaiolClasseMaterial.codigo == codigo).first()
        if not exists:
            db.add(
                PaiolClasseMaterial(
                    codigo=codigo,
                    nome=nome,
                    descricao=descricao,
                    grupo_compatibilidade=grupo,
                )
            )
    db.commit()
    print("Classes de material (seed): OK")
    print("Tipos de material suportados:", ", ".join(t.value for t in TipoMaterialPaiol))


def main():
    create_tables()
    db = SessionLocal()
    try:
        seed_classes(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
