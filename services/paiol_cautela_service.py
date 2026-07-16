"""Serviço de cautelas do módulo Paiol."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session, joinedload

from models import (
    PaiolCautela,
    PaiolCautelaItem,
    PaiolMaterial,
    PaiolMunicao,
    PaiolTipoMaterial,
    StatusUsuarioEnum,
    User,
)
from paiol_constants import (
    CAUTELA_ABAS_EQUIPAMENTO,
    CAUTELA_CATEGORIAS_GRID,
    CategoriaTipoMaterial,
    StatusCautelaPaiol,
    TipoMaterialPaiol,
)
from services.paiol_custodia_service import registrar_evento


class PaiolCautelaError(Exception):
    pass


_cautela_schema_ready = False


def _ensure_cautela_schema() -> None:
    global _cautela_schema_ready
    if _cautela_schema_ready:
        return
    try:
        from sqlalchemy import inspect, text

        from database import engine

        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "paiol_cautelas" not in tables:
            PaiolCautela.__table__.create(bind=engine, checkfirst=True)
        if "paiol_cautela_itens" not in tables:
            PaiolCautelaItem.__table__.create(bind=engine, checkfirst=True)
        if "users" in tables:
            cols = {c["name"] for c in insp.get_columns("users")}
            if "matricula" not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN matricula VARCHAR(30)"))
        if "paiol_cautela_itens" in insp.get_table_names():
            item_cols = {c["name"] for c in insp.get_columns("paiol_cautela_itens")}
            if "quantidade" not in item_cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE paiol_cautela_itens ADD COLUMN quantidade INTEGER"))
        if "paiol_cautelas" in insp.get_table_names():
            cautela_cols = {c["name"] for c in insp.get_columns("paiol_cautelas")}
            if "cautela_fixa" not in cautela_cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE paiol_cautelas "
                            "ADD COLUMN cautela_fixa BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
        _cautela_schema_ready = True
    except Exception:
        pass


def _quantidade_reservada_municao(
    db: Session,
    municao_id: int,
    *,
    exclude_cautela_id: int | None = None,
) -> int:
    """Soma quantidades em cautelas ativas/pendentes da munição."""
    q = (
        db.query(PaiolCautelaItem)
        .join(PaiolCautela)
        .filter(
            PaiolCautelaItem.origem_tipo == "municao",
            PaiolCautelaItem.origem_id == municao_id,
            PaiolCautela.status.in_(
                [StatusCautelaPaiol.ATIVA.value, StatusCautelaPaiol.PENDENTE.value]
            ),
        )
    )
    if exclude_cautela_id:
        q = q.filter(PaiolCautela.id != exclude_cautela_id)
    total = 0
    for item in q.all():
        total += int(item.quantidade or 0)
    return total


def saldo_municao_disponivel(
    db: Session,
    municao: PaiolMunicao,
    *,
    exclude_cautela_id: int | None = None,
) -> dict:
    cadastrado = int(municao.quantidade_valor or 0)
    reservado = _quantidade_reservada_municao(db, municao.id, exclude_cautela_id=exclude_cautela_id)
    disponivel = max(0, cadastrado - reservado)
    return {
        "quantidade_cadastrada": cadastrado,
        "quantidade_reservada": reservado,
        "quantidade_disponivel": disponivel,
        "quantidade_tipo": municao.quantidade_tipo or "unidade",
    }


def _ids_equipamentos_cautelados(
    db: Session,
    orgao_id: int,
    *,
    exclude_cautela_id: int | None = None,
) -> set[tuple[str, int]]:
    """Equipamentos unitários já vinculados a cautelas ativas/pendentes."""
    q = (
        db.query(PaiolCautelaItem.origem_tipo, PaiolCautelaItem.origem_id)
        .join(PaiolCautela)
        .filter(
            PaiolCautela.orgao_id == orgao_id,
            PaiolCautela.status.in_(
                [StatusCautelaPaiol.ATIVA.value, StatusCautelaPaiol.PENDENTE.value]
            ),
            PaiolCautelaItem.origem_tipo.in_(["material", "tipo_material"]),
        )
    )
    if exclude_cautela_id:
        q = q.filter(PaiolCautela.id != exclude_cautela_id)
    return {(origem_tipo, origem_id) for origem_tipo, origem_id in q.all()}


def _equipamento_ja_cautelado(
    db: Session,
    orgao_id: int,
    origem_tipo: str,
    origem_id: int,
    *,
    exclude_cautela_id: int | None = None,
) -> bool:
    if origem_tipo == "municao":
        return False
    return (origem_tipo, origem_id) in _ids_equipamentos_cautelados(
        db, orgao_id, exclude_cautela_id=exclude_cautela_id
    )


def matricula_servidor(user: User | None) -> str:
    if not user:
        return "—"
    if getattr(user, "matricula", None):
        return user.matricula
    return user.cpf or "—"


def listar_servidores_habilitados(db: Session, orgao_id: int, q: str | None = None) -> list[User]:
    """Lista servidores habilitados. Filtro futuro por tipo de equipamento."""
    query = (
        db.query(User)
        .filter(
            User.orgao_id == orgao_id,
            User.status == StatusUsuarioEnum.ATIVO,
        )
        .order_by(User.nome)
    )
    termo = (q or "").strip().lower()
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            (User.nome.ilike(like))
            | (User.matricula.ilike(like))
            | (User.cpf.ilike(like.replace(".", "").replace("-", "")))
        )
    return query.limit(50).all()


def _label_material(material: PaiolMaterial) -> str:
    partes = [material.nome]
    if material.codigo:
        partes.append(f"({material.codigo})")
    return " ".join(partes)


def _label_municao(municao: PaiolMunicao) -> str:
    partes = [municao.nome_comercial or municao.calibre]
    if municao.codigo:
        partes.append(f"({municao.codigo})")
    if municao.lote:
        partes.append(f"Lote {municao.lote}")
    return " — ".join(partes)


def _label_tipo_material(tipo: PaiolTipoMaterial) -> str:
    partes = [tipo.especie]
    if tipo.codigo:
        partes.append(f"({tipo.codigo})")
    return " ".join(partes)


def listar_equipamentos_categoria(
    db: Session,
    ctx: dict,
    categoria: str,
    q: str | None = None,
    *,
    exclude_cautela_id: int | None = None,
) -> list[dict]:
    _ensure_cautela_schema()
    termo = (q or "").strip().lower()
    itens: list[dict] = []
    cautelados = _ids_equipamentos_cautelados(
        db, ctx["orgao_id"], exclude_cautela_id=exclude_cautela_id
    )

    def _match(texto: str) -> bool:
        return not termo or termo in texto.lower()

    def _disponivel_unitario(origem_tipo: str, origem_id: int) -> bool:
        return (origem_tipo, origem_id) not in cautelados

    if categoria == "armamento":
        rows = (
            db.query(PaiolMaterial)
            .filter(
                PaiolMaterial.orgao_id == ctx["orgao_id"],
                PaiolMaterial.tipo == TipoMaterialPaiol.ARMA.value,
                PaiolMaterial.ativo == True,
            )
            .order_by(PaiolMaterial.nome)
            .all()
        )
        for row in rows:
            if not _disponivel_unitario("material", row.id):
                continue
            label = _label_material(row)
            if _match(label):
                itens.append(
                    {
                        "id": row.id,
                        "origem_tipo": "material",
                        "categoria": categoria,
                        "label": label,
                        "codigo": row.codigo,
                    }
                )
    elif categoria == "municao":
        rows = (
            db.query(PaiolMunicao)
            .filter(PaiolMunicao.ativo == True)
            .order_by(PaiolMunicao.nome_comercial)
            .all()
        )
        for row in rows:
            saldo = saldo_municao_disponivel(db, row, exclude_cautela_id=exclude_cautela_id)
            if saldo["quantidade_disponivel"] < 1:
                continue
            label = _label_municao(row)
            if _match(label):
                itens.append(
                    {
                        "id": row.id,
                        "origem_tipo": "municao",
                        "categoria": categoria,
                        "label": label,
                        "codigo": row.codigo,
                        "exige_quantidade": True,
                        **saldo,
                    }
                )
    elif categoria == "acessorio_epi":
        materiais = (
            db.query(PaiolMaterial)
            .filter(
                PaiolMaterial.orgao_id == ctx["orgao_id"],
                PaiolMaterial.tipo == TipoMaterialPaiol.ACESSORIO.value,
                PaiolMaterial.ativo == True,
            )
            .order_by(PaiolMaterial.nome)
            .all()
        )
        for row in materiais:
            if not _disponivel_unitario("material", row.id):
                continue
            label = _label_material(row)
            if _match(label):
                itens.append(
                    {
                        "id": row.id,
                        "origem_tipo": "material",
                        "categoria": categoria,
                        "label": label,
                        "codigo": row.codigo,
                    }
                )
        tipos = (
            db.query(PaiolTipoMaterial)
            .filter(
                PaiolTipoMaterial.categoria == CategoriaTipoMaterial.EPI.value,
                PaiolTipoMaterial.ativo == True,
            )
            .order_by(PaiolTipoMaterial.especie)
            .all()
        )
        for row in tipos:
            if not _disponivel_unitario("tipo_material", row.id):
                continue
            label = _label_tipo_material(row)
            if _match(label):
                itens.append(
                    {
                        "id": row.id,
                        "origem_tipo": "tipo_material",
                        "categoria": categoria,
                        "label": label,
                        "codigo": row.codigo,
                    }
                )
    elif categoria == "sistemas_opticos":
        tipos = (
            db.query(PaiolTipoMaterial)
            .filter(
                PaiolTipoMaterial.categoria == CategoriaTipoMaterial.SISTEMAS_OPTICOS.value,
                PaiolTipoMaterial.ativo == True,
            )
            .order_by(PaiolTipoMaterial.especie)
            .all()
        )
        for row in tipos:
            if not _disponivel_unitario("tipo_material", row.id):
                continue
            label = _label_tipo_material(row)
            if _match(label):
                itens.append(
                    {
                        "id": row.id,
                        "origem_tipo": "tipo_material",
                        "categoria": categoria,
                        "label": label,
                        "codigo": row.codigo,
                    }
                )
    else:
        raise PaiolCautelaError("Categoria de equipamento inválida.")

    return itens


def resumo_cautela(cautela: PaiolCautela) -> dict[str, str]:
    grupos = {"armamento": [], "municao": [], "acessorio_epi": []}
    for item in cautela.itens:
        coluna = CAUTELA_CATEGORIAS_GRID.get(item.categoria, "acessorio_epi")
        texto = item.descricao
        if item.categoria == "municao" and item.quantidade:
            texto = f"{item.descricao} (qtd {item.quantidade})"
        grupos[coluna].append(texto)
    return {k: ", ".join(v) if v else "—" for k, v in grupos.items()}


def listar_cautelas(db: Session, orgao_id: int) -> list[PaiolCautela]:
    _ensure_cautela_schema()
    return (
        db.query(PaiolCautela)
        .options(
            joinedload(PaiolCautela.servidor),
            joinedload(PaiolCautela.itens),
        )
        .filter(PaiolCautela.orgao_id == orgao_id)
        .order_by(PaiolCautela.created_at.desc())
        .all()
    )


def obter_cautela(db: Session, cautela_id: int, orgao_id: int) -> PaiolCautela:
    _ensure_cautela_schema()
    cautela = (
        db.query(PaiolCautela)
        .options(joinedload(PaiolCautela.servidor), joinedload(PaiolCautela.itens))
        .filter(PaiolCautela.id == cautela_id, PaiolCautela.orgao_id == orgao_id)
        .first()
    )
    if not cautela:
        raise PaiolCautelaError("Cautela não encontrada.")
    return cautela


def _validar_itens(
    db: Session,
    ctx: dict,
    itens_payload: list[dict],
    *,
    exclude_cautela_id: int | None = None,
) -> list[dict]:
    if not itens_payload:
        raise PaiolCautelaError("Selecione ao menos um equipamento.")
    validados = []
    vistos: set[tuple[str, str, int]] = set()
    for raw in itens_payload:
        categoria = (raw.get("categoria") or "").strip()
        origem_tipo = (raw.get("origem_tipo") or "").strip()
        origem_id = raw.get("origem_id")
        descricao = (raw.get("descricao") or "").strip()
        quantidade = raw.get("quantidade")
        if categoria not in {a["key"] for a in CAUTELA_ABAS_EQUIPAMENTO}:
            raise PaiolCautelaError("Categoria de equipamento inválida.")
        if origem_tipo not in {"material", "municao", "tipo_material"}:
            raise PaiolCautelaError("Origem de equipamento inválida.")
        try:
            origem_id = int(origem_id)
        except (TypeError, ValueError):
            raise PaiolCautelaError("Equipamento inválido.")
        chave = (categoria, origem_tipo, origem_id)
        if chave in vistos:
            continue
        vistos.add(chave)

        qtd_final = None
        if origem_tipo == "material":
            material = (
                db.query(PaiolMaterial)
                .filter(PaiolMaterial.id == origem_id, PaiolMaterial.orgao_id == ctx["orgao_id"], PaiolMaterial.ativo == True)
                .first()
            )
            if not material:
                raise PaiolCautelaError("Material não encontrado ou inativo.")
            descricao = descricao or _label_material(material)
            if _equipamento_ja_cautelado(
                db, ctx["orgao_id"], origem_tipo, origem_id, exclude_cautela_id=exclude_cautela_id
            ):
                raise PaiolCautelaError(f"O equipamento “{descricao}” já está cautelado.")
        elif origem_tipo == "municao":
            municao = db.query(PaiolMunicao).filter(PaiolMunicao.id == origem_id, PaiolMunicao.ativo == True).first()
            if not municao:
                raise PaiolCautelaError("Munição não encontrada ou inativa.")
            descricao = descricao or _label_municao(municao)
            try:
                qtd_final = int(quantidade)
            except (TypeError, ValueError):
                raise PaiolCautelaError(f"Informe a quantidade para a munição “{descricao}”.")
            if qtd_final < 1:
                raise PaiolCautelaError(f"A quantidade da munição “{descricao}” deve ser maior que zero.")
            saldo = saldo_municao_disponivel(db, municao, exclude_cautela_id=exclude_cautela_id)
            if qtd_final > saldo["quantidade_disponivel"]:
                raise PaiolCautelaError(
                    f"Quantidade de “{descricao}” ({qtd_final}) excede o disponível "
                    f"({saldo['quantidade_disponivel']} de {saldo['quantidade_cadastrada']} cadastradas)."
                )
        else:
            tipo = db.query(PaiolTipoMaterial).filter(PaiolTipoMaterial.id == origem_id, PaiolTipoMaterial.ativo == True).first()
            if not tipo:
                raise PaiolCautelaError("Tipo de material não encontrado ou inativo.")
            descricao = descricao or _label_tipo_material(tipo)
            if _equipamento_ja_cautelado(
                db, ctx["orgao_id"], origem_tipo, origem_id, exclude_cautela_id=exclude_cautela_id
            ):
                raise PaiolCautelaError(f"O equipamento “{descricao}” já está cautelado.")

        validados.append(
            {
                "categoria": categoria,
                "origem_tipo": origem_tipo,
                "origem_id": origem_id,
                "descricao": descricao[:300],
                "quantidade": qtd_final,
            }
        )
    return validados


def _aplicar_itens(cautela: PaiolCautela, itens: list[dict]) -> None:
    cautela.itens.clear()
    for item in itens:
        cautela.itens.append(
            PaiolCautelaItem(
                categoria=item["categoria"],
                origem_tipo=item["origem_tipo"],
                origem_id=item["origem_id"],
                descricao=item["descricao"],
                quantidade=item.get("quantidade"),
            )
        )


def criar_cautela(
    db: Session,
    ctx: dict,
    servidor_id: int,
    itens_payload: list[dict],
    observacao: str | None = None,
    status: str | None = None,
    cautela_fixa: bool = False,
) -> PaiolCautela:
    _ensure_cautela_schema()
    servidor = (
        db.query(User)
        .filter(
            User.id == servidor_id,
            User.orgao_id == ctx["orgao_id"],
            User.status == StatusUsuarioEnum.ATIVO,
        )
        .first()
    )
    if not servidor:
        raise PaiolCautelaError("Selecione um servidor habilitado.")

    itens = _validar_itens(db, ctx, itens_payload)
    status_final = status or StatusCautelaPaiol.ATIVA.value
    if status_final not in {s.value for s in StatusCautelaPaiol}:
        raise PaiolCautelaError("Status inválido.")

    cautela = PaiolCautela(
        orgao_id=ctx["orgao_id"],
        municipio_id=ctx["municipio_id"],
        servidor_id=servidor_id,
        status=status_final,
        cautela_fixa=bool(cautela_fixa),
        observacao=(observacao or "").strip() or None,
        created_by=ctx["user_id"],
    )
    _aplicar_itens(cautela, itens)
    db.add(cautela)
    db.flush()

    detalhes = f"Cautela #{cautela.id} — servidor {matricula_servidor(servidor)} {servidor.nome}"
    for item in itens:
        if item["origem_tipo"] == "material":
            registrar_evento(
                db,
                ctx,
                "CAUTELA",
                material_id=item["origem_id"],
                documento_ref=f"CAUTELA#{cautela.id}",
                detalhes=f"{detalhes}. {item['descricao']}",
            )
    db.commit()
    db.refresh(cautela)
    return cautela


def atualizar_cautela(
    db: Session,
    ctx: dict,
    cautela_id: int,
    servidor_id: int,
    itens_payload: list[dict],
    observacao: str | None = None,
    status: str | None = None,
    cautela_fixa: bool = False,
) -> PaiolCautela:
    cautela = obter_cautela(db, cautela_id, ctx["orgao_id"])
    if cautela.status == StatusCautelaPaiol.BAIXADA.value:
        raise PaiolCautelaError("Cautelas baixadas não podem ser editadas.")

    servidor = (
        db.query(User)
        .filter(
            User.id == servidor_id,
            User.orgao_id == ctx["orgao_id"],
            User.status == StatusUsuarioEnum.ATIVO,
        )
        .first()
    )
    if not servidor:
        raise PaiolCautelaError("Selecione um servidor habilitado.")

    itens = _validar_itens(db, ctx, itens_payload, exclude_cautela_id=cautela_id)
    status_final = status or cautela.status
    if status_final not in {s.value for s in StatusCautelaPaiol}:
        raise PaiolCautelaError("Status inválido.")
    if status_final == StatusCautelaPaiol.BAIXADA.value:
        raise PaiolCautelaError("Use a ação Dar baixa para encerrar a cautela.")

    cautela.servidor_id = servidor_id
    cautela.observacao = (observacao or "").strip() or None
    cautela.status = status_final
    cautela.cautela_fixa = bool(cautela_fixa)
    _aplicar_itens(cautela, itens)
    db.commit()
    db.refresh(cautela)
    return cautela


def excluir_cautela(db: Session, ctx: dict, cautela_id: int) -> None:
    cautela = obter_cautela(db, cautela_id, ctx["orgao_id"])
    if cautela.status == StatusCautelaPaiol.BAIXADA.value:
        raise PaiolCautelaError("Cautelas baixadas não podem ser excluídas.")
    db.delete(cautela)
    db.commit()


def dar_baixa_cautela(db: Session, ctx: dict, cautela_id: int) -> PaiolCautela:
    cautela = obter_cautela(db, cautela_id, ctx["orgao_id"])
    if cautela.status == StatusCautelaPaiol.BAIXADA.value:
        raise PaiolCautelaError("Esta cautela já está baixada.")
    cautela.status = StatusCautelaPaiol.BAIXADA.value
    from dependencies import agora_brasilia

    cautela.baixada_em = agora_brasilia()
    cautela.baixada_por = ctx["user_id"]
    detalhes = f"Baixa cautela #{cautela.id} — servidor {matricula_servidor(cautela.servidor)}"
    for item in cautela.itens:
        if item.origem_tipo == "material":
            registrar_evento(
                db,
                ctx,
                "DEVOLUCAO",
                material_id=item.origem_id,
                documento_ref=f"CAUTELA#{cautela.id}",
                detalhes=detalhes,
            )
    db.commit()
    db.refresh(cautela)
    return cautela


def parse_itens_json(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise PaiolCautelaError("Equipamentos inválidos.")
    if not isinstance(data, list):
        raise PaiolCautelaError("Equipamentos inválidos.")
    return data


def cautela_para_form(cautela: PaiolCautela) -> dict:
    return {
        "id": cautela.id,
        "servidor_id": cautela.servidor_id,
        "servidor_nome": cautela.servidor.nome if cautela.servidor else "",
        "servidor_matricula": matricula_servidor(cautela.servidor),
        "status": cautela.status,
        "cautela_fixa": bool(cautela.cautela_fixa),
        "observacao": cautela.observacao or "",
        "itens": [
            {
                "categoria": i.categoria,
                "origem_tipo": i.origem_tipo,
                "origem_id": i.origem_id,
                "descricao": i.descricao,
                "quantidade": i.quantidade,
                "key": f"{i.categoria}:{i.origem_tipo}:{i.origem_id}",
            }
            for i in cautela.itens
        ],
    }
