"""Cria tabelas do módulo Paiol e dados iniciais de cadastro."""

from database import Base, SessionLocal, engine

import models  # noqa: F401
from models import PaiolClasseMaterial
from paiol_constants import TipoMaterialPaiol

TABLES = [
    "paiol_classes_material",
    "paiol_fabricantes",
    "paiol_fornecedores",
    "paiol_depositos",
    "paiol_localizacoes",
    "paiol_materiais",
    "paiol_lotes",
    "paiol_itens",
    "paiol_saldos",
    "paiol_movimentacoes",
    "paiol_usuarios_autorizados",
    "paiol_custodia_eventos",
    "paiol_dashboard_atalhos",
    "paiol_requisicoes",
    "paiol_requisicao_itens",
    "paiol_assinaturas",
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
