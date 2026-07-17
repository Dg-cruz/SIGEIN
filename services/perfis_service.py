"""Schema e helpers para perfis personalizados e permissões por módulo."""

from __future__ import annotations

from models import PerfilEnum

_perfis_schema_ready = False

# Perfis do sistema (espelham PerfilEnum) — sincronizados no startup
PERFIS_SISTEMA = [
    (
        PerfilEnum.MASTER.value,
        "MASTER",
        "Acesso total ao sistema. Gerencia múltiplos municípios e configurações globais.",
    ),
    (
        PerfilEnum.ADMIN_MUNICIPAL.value,
        "ADMIN MUNICIPAL",
        "Acesso total ao município. Gerencia usuários, inventário e protocolo.",
    ),
    (
        PerfilEnum.GESTOR_ESTOQUE.value,
        "GESTOR DE ESTOQUE",
        "Acesso total ao inventário do órgão. Gera relatórios. Não acessa protocolo.",
    ),
    (
        PerfilEnum.GESTOR_PROTOCOLO.value,
        "GESTOR DE PROTOCOLO",
        "Acesso total ao protocolo. Cria e tramita processos. Não acessa inventário.",
    ),
    (
        PerfilEnum.GESTOR_GERAL.value,
        "GESTOR GERAL",
        "Combina Estoque + Protocolo. Visão 360° do órgão. Não gerencia usuários.",
    ),
    (
        PerfilEnum.GESTOR_SEGEM.value,
        "GESTOR SEGEM",
        "Acesso ao módulo SEGEM (gestão de materiais).",
    ),
    (
        PerfilEnum.OPERADOR.value,
        "OPERADOR",
        "Acesso básico. Consulta e ações limitadas. Não pode criar/editar/excluir.",
    ),
]


def _seed_perfis_sistema() -> None:
    """Garante que os perfis do PerfilEnum existam na tabela perfis."""
    from database import SessionLocal
    from models import Perfil

    db = SessionLocal()
    try:
        for codigo, nome, descricao in PERFIS_SISTEMA:
            existente = (
                db.query(Perfil)
                .filter((Perfil.codigo == codigo) | (Perfil.nome == nome))
                .first()
            )
            if existente:
                if not existente.codigo:
                    existente.codigo = codigo
                existente.sistema = True
                if not existente.descricao:
                    existente.descricao = descricao
                if existente.nome != nome and existente.codigo == codigo:
                    # Mantém nome canônico dos perfis de sistema
                    conflito = (
                        db.query(Perfil)
                        .filter(Perfil.nome == nome, Perfil.id != existente.id)
                        .first()
                    )
                    if not conflito:
                        existente.nome = nome
            else:
                db.add(
                    Perfil(
                        codigo=codigo,
                        nome=nome,
                        descricao=descricao,
                        ativo=True,
                        sistema=True,
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _ensure_perfis_schema() -> None:
    """Cria tabelas/colunas de perfis se ainda não existirem (idempotente)."""
    global _perfis_schema_ready
    if _perfis_schema_ready:
        try:
            _seed_perfis_sistema()
        except Exception:
            pass
        return
    try:
        from sqlalchemy import inspect, text

        from database import engine
        from models import Perfil, PerfilPermissao

        insp = inspect(engine)
        tables = set(insp.get_table_names())

        if "perfis" not in tables:
            Perfil.__table__.create(bind=engine, checkfirst=True)
        if "perfil_permissoes" not in tables:
            PerfilPermissao.__table__.create(bind=engine, checkfirst=True)

        if "perfis" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("perfis")}
            with engine.begin() as conn:
                if "codigo" not in cols:
                    conn.execute(text("ALTER TABLE perfis ADD COLUMN codigo VARCHAR(50)"))
                if "sistema" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE perfis ADD COLUMN sistema BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )

        if "users" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("users")}
            if "perfil_personalizado_id" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE users "
                            "ADD COLUMN perfil_personalizado_id INTEGER "
                            "REFERENCES perfis(id)"
                        )
                    )

        _seed_perfis_sistema()
        _perfis_schema_ready = True
    except Exception:
        pass
